document.addEventListener('DOMContentLoaded', () => {
    const createModal = document.getElementById('helpMessageCreateModal');
    const detailModal = document.getElementById('helpMessageDetailModal');
    const replyModal = document.getElementById('helpMessageReplyModal');
    const sumillaModal = document.getElementById('helpMessageSumillaModal');
    const closeModalEl = document.getElementById('helpMessageCloseModal');
    const replyForm = document.getElementById('replyHelpMessageForm');
    const sumillaForm = document.getElementById('sumillaHelpMessageForm');
    const closeForm = document.getElementById('closeHelpMessageForm');
    const unreadBadge = document.getElementById('helpMessagesBadge');

    const closeModal = (modal) => {
        if (!modal) return;
        modal.classList.add('hidden');
    };

    const openModal = (modal) => {
        if (!modal) return;
        modal.classList.remove('hidden');
    };

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
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': window.getCookie ? window.getCookie('csrftoken') : '',
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
                    if ((payload.status || '').toLowerCase() === 'finalized') {
                        statusCell.innerHTML = '<span class="status-badge active">Finalizado</span>';
                    } else {
                        statusCell.innerHTML = '<span class="status-badge badge-neutral">En Revisión</span>';
                    }
                }
                if (row.dataset.userTurn === '1') {
                    row.querySelectorAll('.js-read-gated').forEach((actionBtn) => {
                        actionBtn.style.display = '';
                    });
                }

                const hiddenTimeline = row.querySelector(`#conversation-thread-${rowId.replace('message-row-', '')}`);
                if (hiddenTimeline) {
                    hiddenTimeline.querySelectorAll('.js-unread-indicator').forEach((unreadNode) => {
                        unreadNode.classList.remove('js-unread-indicator', 'conversation-body-unread');
                        if (unreadNode.classList.contains('msg-read-badge')) {
                            unreadNode.textContent = 'Leído';
                            unreadNode.classList.remove('pending', 'pending-own', 'pending-other');
                            unreadNode.classList.add('read');
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
            openModal(createModal);
        },
        openDetail(button) {
            const detailSubject = document.getElementById('detailMessageSubject');
            const detailSender = document.getElementById('detailMessageSender');
            const detailRecipient = document.getElementById('detailMessageRecipient');
            const detailCreatedAt = document.getElementById('detailMessageCreatedAt');
            const detailStatus = document.getElementById('detailMessageStatus');
            const detailConversationTimeline = document.getElementById('detailConversationTimeline');
            const conversationId = button.dataset.conversationId;
            const threadTemplate = conversationId ? document.getElementById(`conversation-thread-${conversationId}`) : null;

            detailSubject.textContent = button.dataset.subject || '';
            detailSender.textContent = button.dataset.sender || '';
            detailRecipient.textContent = button.dataset.recipient || '';
            detailCreatedAt.textContent = button.dataset.createdAt || '';
            detailStatus.textContent = button.dataset.statusLabel || '';

            if (detailConversationTimeline) {
                if (threadTemplate) {
                    detailConversationTimeline.innerHTML = threadTemplate.innerHTML;
                } else {
                    detailConversationTimeline.innerHTML = '<p>No hay historial disponible.</p>';
                }
            }

            if ((button.dataset.statusLabel || '').toLowerCase() !== 'atendido') {
                const rowId = `message-row-${conversationId}`;
                const row = document.getElementById(rowId);
                if (row && row.dataset.userTurn === '1') {
                    row.querySelectorAll('.js-read-gated').forEach((actionBtn) => {
                        actionBtn.style.display = '';
                    });
                }
                markAsRead(button.dataset.markReadUrl, rowId);
                if (detailConversationTimeline) {
                    detailConversationTimeline.querySelectorAll('.js-unread-indicator').forEach((unreadNode) => {
                        unreadNode.classList.remove('js-unread-indicator', 'conversation-body-unread');
                        if (unreadNode.classList.contains('msg-read-badge')) {
                            unreadNode.textContent = 'Leído';
                            unreadNode.classList.remove('pending', 'pending-own', 'pending-other');
                            unreadNode.classList.add('read');
                        }
                    });
                }
            } else {
                detailStatus.textContent = 'Atendido';
            }
            openModal(detailModal);
        },
        openReply(button) {
            const originalId = document.getElementById('replyOriginalMessageId');
            const replySender = document.getElementById('replyMessageSender');
            const replyOriginalSubject = document.getElementById('replyOriginalSubject');
            const replyGeneratedSubject = document.getElementById('replyGeneratedSubject');

            originalId.value = button.dataset.messageId || '';
            replySender.textContent = button.dataset.sender || '';
            replyOriginalSubject.textContent = button.dataset.subject || '';
            replyGeneratedSubject.textContent = `Respuesta a mensaje: ${button.dataset.subject || ''}`;
            replyForm.action = button.dataset.replyUrl || replyForm.action;
            openModal(replyModal);
        },
        openSumilla(button) {
            const originalId = document.getElementById('sumillaOriginalMessageId');
            const originalSubject = document.getElementById('sumillaOriginalSubject');

            if (originalId) {
                originalId.value = button.dataset.messageId || '';
            }
            if (originalSubject) {
                originalSubject.textContent = button.dataset.subject || '';
            }
            if (sumillaForm) {
                sumillaForm.action = button.dataset.sumillaUrl || sumillaForm.action;
            }
            openModal(sumillaModal);
        },
        openClose(button) {
            const closeOriginalId = document.getElementById('closeOriginalMessageId');
            const closeOriginalSubject = document.getElementById('closeOriginalSubject');

            if (closeOriginalId) {
                closeOriginalId.value = button.dataset.conversationId || '';
            }
            if (closeOriginalSubject) {
                closeOriginalSubject.textContent = button.dataset.subject || '';
            }
            if (closeForm) {
                closeForm.action = button.dataset.closeUrl || closeForm.action;
            }
            openModal(closeModalEl);
        },
        closeAll() {
            closeModal(createModal);
            closeModal(detailModal);
            closeModal(replyModal);
            closeModal(sumillaModal);
            closeModal(closeModalEl);
        }
    };

    document.querySelectorAll('.js-close-modal').forEach((button) => {
        button.addEventListener('click', () => {
            window.helpMessagesActions.closeAll();
        });
    });

    [createModal, detailModal, replyModal, sumillaModal, closeModalEl].forEach((modal) => {
        if (!modal) return;
        modal.addEventListener('click', (event) => {
            if (event.target === modal) {
                closeModal(modal);
            }
        });
    });

    if (window.$ && window.$.fn && window.$.fn.select2) {
        const sumillaRecipient = window.$('#id_help_sumilla_recipient');
        if (sumillaRecipient.length) {
            sumillaRecipient.select2({
                width: '100%',
                dropdownParent: window.$('#helpMessageSumillaModal')
            });
        }
    }
});
