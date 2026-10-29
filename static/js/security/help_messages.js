document.addEventListener('DOMContentLoaded', () => {
    const detailFinalizeForm = document.getElementById('detailFinalizeForm');
    const detailFinalizeBtn = document.getElementById('detailFinalizeBtn');
    const detailCorrectionBtn = document.getElementById('detailCorrectionBtn');
    const unreadBadge = document.getElementById('helpMessagesBadge');

    const syncUnreadBadge = (remaining) => {
        if (!unreadBadge) return;
        if (remaining > 0) {
            unreadBadge.textContent = remaining;
            unreadBadge.classList.remove('hidden');
        } else {
            unreadBadge.classList.add('hidden');
        }
    };

    const markAsRead = async (url, rowId) => {
        if (!url) return;
        try {
            const csrf = typeof getCSRF === 'function' ? getCSRF() : '';
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrf,
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            if (!response.ok) return;
            const payload = await response.json();
            const row = rowId ? document.getElementById(rowId) : null;
            if (row) {
                row.dataset.status = payload.status || 'read';
                row.classList.remove('conversation-unread');
                const statusCell = row.querySelector('td:nth-child(7)');
                if (statusCell) {
                    const nextStatus = (payload.status || '').toLowerCase();
                    if (nextStatus === 'finalized' || nextStatus === 'attended') {
                        statusCell.innerHTML = '<span class="badge badge-green">Finalizado</span>';
                    } else if (nextStatus === 'sent') {
                        statusCell.innerHTML = '<span class="badge badge-red">En Proceso</span>';
                    } else {
                        statusCell.innerHTML = '<span class="badge badge-yellow">En Revisión</span>';
                    }
                }
                if (row.dataset.userTurn === '1') {
                    row.querySelectorAll('.js-read-gated').forEach(btn => btn.style.display = '');
                }

                const hiddenTimeline = row.querySelector(`#conversation-thread-${rowId.replace('message-row-', '')}`);
                if (hiddenTimeline) {
                    hiddenTimeline.querySelectorAll('.js-unread-indicator').forEach(node => {
                        node.classList.remove('js-unread-indicator', 'conversation-body-unread');
                        if (node.classList.contains('badge')) {
                            node.textContent = 'Leído';
                            node.className = 'badge badge-green';
                        }
                    });
                }
            }
            if (typeof payload.remaining_unread === 'number') {
                syncUnreadBadge(payload.remaining_unread);
            }
        } catch (error) {
            console.error('Error marcando mensaje como leído:', error);
        }
    };

    window.helpMessagesActions = {
        openCreate() {
            window.openModal('helpMessageCreateModal');
        },

        openDetail(button) {
            const detailSubject = document.getElementById('detailMessageSubject');
            const detailSender = document.getElementById('detailMessageSender');
            const detailRecipient = document.getElementById('detailMessageRecipient');
            const detailCreatedAt = document.getElementById('detailMessageCreatedAt');
            const detailStatus = document.getElementById('detailMessageStatus');
            const detailTimeline = document.getElementById('detailConversationTimeline');
            const conversationId = button.dataset.conversationId;
            const threadTemplate = conversationId ? document.getElementById(`conversation-thread-${conversationId}`) : null;

            if (detailSubject) detailSubject.textContent = button.dataset.subject || '-';
            if (detailSender) detailSender.textContent = button.dataset.sender || '-';
            if (detailRecipient) detailRecipient.textContent = button.dataset.recipient || '-';
            if (detailCreatedAt) detailCreatedAt.textContent = button.dataset.createdAt || '-';
            if (detailStatus) detailStatus.textContent = button.dataset.statusLabel || '-';

            if (detailTimeline) {
                detailTimeline.innerHTML = threadTemplate ? threadTemplate.innerHTML : '<p class="text-muted">No hay historial disponible.</p>';
            }

            const canShowAttended = button.dataset.showAttendedActions === '1';
            if (detailFinalizeForm && detailFinalizeBtn) {
                detailFinalizeForm.style.display = canShowAttended ? '' : 'none';
                detailFinalizeForm.action = canShowAttended ? (button.dataset.finalizeUrl || '#') : '#';
            }
            if (detailCorrectionBtn) {
                detailCorrectionBtn.style.display = canShowAttended ? '' : 'none';
                if (canShowAttended) {
                    detailCorrectionBtn.dataset.messageId = conversationId || '';
                    detailCorrectionBtn.dataset.subject = button.dataset.subject || '';
                    detailCorrectionBtn.dataset.sender = button.dataset.correctionTarget || button.dataset.sender || '';
                    detailCorrectionBtn.dataset.replyUrl = button.dataset.correctionUrl || '#';
                }
            }

            if ((button.dataset.statusLabel || '').toLowerCase() !== 'finalizado') {
                const rowId = `message-row-${conversationId}`;
                const row = document.getElementById(rowId);
                if (row && row.dataset.userTurn === '1') {
                    row.querySelectorAll('.js-read-gated').forEach(btn => btn.style.display = '');
                }
                markAsRead(button.dataset.markReadUrl, rowId);
            }

            window.openModal('helpMessageDetailModal');
        },

        openReply(button) {
            const originalId = document.getElementById('replyOriginalMessageId');
            const replySender = document.getElementById('replyMessageSender');
            const replyOriginalSubject = document.getElementById('replyOriginalSubject');
            const replyGeneratedSubject = document.getElementById('replyGeneratedSubject');
            const replyForm = document.getElementById('replyHelpMessageForm');

            if (originalId) originalId.value = button.dataset.messageId || '';
            if (replySender) replySender.textContent = button.dataset.sender || '-';
            if (replyOriginalSubject) replyOriginalSubject.textContent = button.dataset.subject || '-';

            const isCorrection = button.dataset.isCorrection === '1';
            if (replyGeneratedSubject) {
                replyGeneratedSubject.textContent = isCorrection
                    ? `Corrección/Alcance: ${button.dataset.subject || ''}`
                    : `Respuesta a mensaje: ${button.dataset.subject || ''}`;
            }

            if (replyForm && button.dataset.replyUrl) {
                replyForm.action = button.dataset.replyUrl;
            }

            window.openModal('helpMessageReplyModal');
        },

        openSumilla(button) {
            const originalId = document.getElementById('sumillaOriginalMessageId');
            const originalSubject = document.getElementById('sumillaOriginalSubject');
            const sumillaForm = document.getElementById('sumillaHelpMessageForm');

            if (originalId) originalId.value = button.dataset.messageId || '';
            if (originalSubject) originalSubject.textContent = button.dataset.subject || '-';
            if (sumillaForm && button.dataset.sumillaUrl) {
                sumillaForm.action = button.dataset.sumillaUrl;
            }

            window.openModal('helpMessageSumillaModal');
        },

        openClose(button) {
            const closeOriginalId = document.getElementById('closeOriginalMessageId');
            const closeOriginalSubject = document.getElementById('closeOriginalSubject');
            const closeForm = document.getElementById('closeHelpMessageForm');

            if (closeOriginalId) closeOriginalId.value = button.dataset.conversationId || '';
            if (closeOriginalSubject) closeOriginalSubject.textContent = button.dataset.subject || '-';
            if (closeForm && button.dataset.closeUrl) {
                closeForm.action = button.dataset.closeUrl;
            }

            window.openModal('helpMessageCloseModal');
        }
    };

    // Botón de corrección desde el modal de detalle
    if (detailCorrectionBtn) {
        detailCorrectionBtn.addEventListener('click', () => {
            const payload = {
                dataset: {
                    messageId: detailCorrectionBtn.dataset.messageId || '',
                    subject: detailCorrectionBtn.dataset.subject || '',
                    sender: detailCorrectionBtn.dataset.sender || '',
                    replyUrl: detailCorrectionBtn.dataset.replyUrl || '',
                    isCorrection: '1'
                }
            };
            window.closeModal('helpMessageDetailModal');
            window.helpMessagesActions.openReply(payload);
        });
    }
});