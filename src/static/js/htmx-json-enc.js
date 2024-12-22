// Handle payment response and redirect
htmx.on('htmx:afterRequest', function (evt) {
    if (evt.detail.pathInfo.requestPath === '/api/state/payment/checkout') {
        console.log('Payment response:', evt.detail.xhr.response);
        try {
            const response = JSON.parse(evt.detail.xhr.response);
            if (response.success && response.data.url) {
                console.log('Redirecting to:', response.data.url);
                window.location.href = response.data.url;
            }
        } catch (error) {
            console.error('Failed to parse payment response:', error);
        }
    }
});