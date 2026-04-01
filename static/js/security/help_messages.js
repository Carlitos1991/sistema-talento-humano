document.addEventListener('DOMContentLoaded', () => {
    const createModal = document.getElementById('helpMessageCreateModal');
    const detailModal = document.getElementById('helpMessageDetailModal');
    const replyModal = document.getElementById('helpMessageReplyModal');
    const replyForm = document.getElementById('replyHelpMessageForm');
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
                const statusCell = row.querySelector('td:nth-child(6)');
                if (statusCell) {
                    statusCell.innerHTML = '<span class="status-badge badge-neutral">Leído</span>';
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
            const detailDetail = document.getElementById('detailMessageDetail');
            const attachmentBox = document.getElementById('detailMessageAttachmentBox');
            const attachmentLink = document.getElementById('detailMessageAttachment');

            detailSubject.textContent = button.dataset.subject || '';
            detailSender.textContent = button.dataset.sender || '';
            detailRecipient.textContent = button.dataset.recipient || '';
            detailCreatedAt.textContent = button.dataset.createdAt || '';
            detailStatus.textContent = button.dataset.statusLabel || '';
            detailDetail.textContent = button.dataset.detail || '';

            if ((button.dataset.statusLabel || '').toLowerCase() === 'enviado') {
                detailStatus.textContent = 'Leído';
            }

            if (button.dataset.attachmentUrl) {
                attachmentBox.style.display = 'block';
                attachmentLink.href = button.dataset.attachmentUrl;
            } else {
                attachmentBox.style.display = 'none';
                attachmentLink.href = '#';
            }

            markAsRead(button.dataset.markReadUrl, `message-row-${button.dataset.messageId}`);
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
        closeAll() {
            closeModal(createModal);
            closeModal(detailModal);
            closeModal(replyModal);
        }
    };

    document.querySelectorAll('.js-close-modal').forEach((button) => {
        button.addEventListener('click', () => {
            window.helpMessagesActions.closeAll();
        });
    });

    [createModal, detailModal, replyModal].forEach((modal) => {
        if (!modal) return;
        modal.addEventListener('click', (event) => {
            if (event.target === modal) {
                closeModal(modal);
            }
        });
    });
});
