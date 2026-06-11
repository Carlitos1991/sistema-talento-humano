/**
 * Captura información del dispositivo y la envía al servidor
 * Intenta obtener la MAC del dispositivo (cuando sea posible)
 */

(function() {
    'use strict';

    /**
     * Obtiene la MAC del dispositivo intentando diferentes métodos
     */
    async function getMACAddress() {
        try {
            // Intentar con WebRTC (IRCandidates)
            const peerConnection = new (window.RTCPeerConnection || 
                                      window.webkitRTCPeerConnection || 
                                      window.mozRTCPeerConnection)({
                iceServers: []
            });
            
            const dataChannel = peerConnection.createDataChannel('');
            
            return new Promise((resolve) => {
                let macFound = false;
                
                // Escuchar candidatos ICE
                peerConnection.onicecandidate = (ice) => {
                    if (!ice || !ice.candidate) {
                        // Sin más candidatos
                        setTimeout(() => {
                            resolve(macFound ? null : 'No disponible');
                        }, 500);
                        return;
                    }
                    
                    const candidate = ice.candidate.candidate;
                    // Buscar patrón de MAC en la candidata
                    const macMatches = candidate.match(/([0-9a-f]{1,2}([:-][0-9a-f]{1,2}){5})/gi);
                    if (macMatches && macMatches.length > 0) {
                        // Filtrar direcciones locales (00:00:00:00:00:00)
                        const mac = macMatches[0];
                        if (mac !== '00:00:00:00:00:00' && mac !== '00-00-00-00-00-00') {
                            macFound = true;
                            resolve(mac);
                            peerConnection.close();
                        }
                    }
                };
                
                // Crear una oferta para disparar candidatos ICE
                try {
                    peerConnection.createOffer()
                        .then(offer => peerConnection.setLocalDescription(offer))
                        .catch(e => {
                            console.debug('Error en WebRTC:', e);
                            resolve('No disponible');
                        });
                } catch (error) {
                    console.debug('WebRTC no soportado');
                    resolve('No disponible');
                }
                
                // Timeout de 3 segundos
                setTimeout(() => {
                    resolve(macFound ? null : 'No disponible');
                }, 3000);
            });
        } catch (e) {
            console.debug('Error obteniendo MAC:', e);
            return 'No disponible';
        }
    }

    /**
     * Obtiene información del navegador/dispositivo
     */
    function getDeviceInfo() {
        return {
            userAgent: navigator.userAgent,
            language: navigator.language,
            platform: navigator.platform,
            screen: `${screen.width}x${screen.height}`,
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        };
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
                    mac_address: macAddress || 'No disponible',
                    device_info: JSON.stringify(deviceInfo),
                })
            });

            if (response.ok) {
                const data = await response.json();
            } else {
                console.error('Error al enviar info del dispositivo:', response.status);
            }
        } catch (e) {
            console.error('Error en sendDeviceInfo:', e);
        }
    }

    // Ejecutar cuando el documento esté listo
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            // Esperar 2 segundos para que se complete el login
            setTimeout(sendDeviceInfo, 2000);
        });
    } else {
        // El documento ya está cargado
        setTimeout(sendDeviceInfo, 2000);
    }

    // También ejecutar después de cada cambio significativo (por si el usuario navega)
    window.addEventListener('load', () => {
        // Esperar un poco después de que todo esté completamente cargado
        setTimeout(() => {
            // Enviar si no se ejecutó aún (fallback)
            if (document.querySelector('body') && !document._deviceInfoSent) {
                sendDeviceInfo();
                document._deviceInfoSent = true;
            }
        }, 3000);
    });
})();
