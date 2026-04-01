/**
 * Captura información del dispositivo y la envía al servidor
 * Intenta obtener la MAC del dispositivo (cuando sea posible)
 */

(function() {
    'use strict';

    /**
     * Obtiene la MAC del dispositivo intentando diferentes métodos
     * Nota: La mayoría de navegadores restringen el acceso a la MAC por seguridad
     */
    async function getMACAddress() {
        try {
            // Método 1: WebRTC (funciona en algunos casos)
            const peerConnection = new (window.RTCPeerConnection || window.webkitRTCPeerConnection)({
                iceServers: []
            });
            const dataChannel = peerConnection.createDataChannel('');
            
            return new Promise((resolve) => {
                peerConnection.createOffer().then(offer => {
                    return peerConnection.setLocalDescription(offer);
                }).catch(e => {
                    resolve('No disponible');
                });

                // Escuchar candidatos ICE para extraer información
                peerConnection.onicecandidate = (ice) => {
                    if (!ice || !ice.candidate) {
                        resolve('No disponible');
                        return;
                    }
                    
                    const candidate = ice.candidate.candidate;
                    // Intenta extraer la dirección MAC de la candidata (raramente funciona)
                    const matches = candidate.match(/([0-9a-f]{1,2}([:-][0-9a-f]{1,2}){5})/gi);
                    if (matches) {
                        resolve(matches[0]);
                    }
                };

                // Timeout después de 2 segundos
                setTimeout(() => {
                    resolve('No disponible');
                }, 2000);
            });
        } catch (e) {
            return 'No disponible';
        }
    }

    /**
     * Obtiene información del navegador
     */
    function getDeviceInfo() {
        return {
            userAgent: navigator.userAgent,
            language: navigator.language,
            platform: navigator.platform,
            hardwareConcurrency: navigator.hardwareConcurrency || 'Desconocido',
            deviceMemory: navigator.deviceMemory || 'Desconocido',
            maxTouchPoints: navigator.maxTouchPoints || 0,
        };
    }

    /**
     * Envía la información capturada al servidor
     */
    async function sendDeviceInfo() {
        try {
            const macAddress = await getMACAddress();
            const deviceInfo = getDeviceInfo();

            // Enviar información al servidor
            const response = await fetch('/security/api/update-session-info/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken'),
                },
                body: JSON.stringify({
                    mac_address: macAddress,
                    device_info: JSON.stringify(deviceInfo),
                })
            });

            if (response.ok) {
                console.log('Información del dispositivo capturada correctamente');
            }
        } catch (e) {
            console.error('Error al capturar información del dispositivo:', e);
        }
    }

    /**
     * Obtiene el valor de una cookie por nombre
     */
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    // Ejecutar cuando el documento esté listo
    document.addEventListener('DOMContentLoaded', () => {
        // Esperar 1 segundo para que se complete el login
        setTimeout(sendDeviceInfo, 1000);
    });
})();
