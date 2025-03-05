$(document).ready(function () {
    const challengeUuid = $('#createContainerBtn').data('challenge-uuid');

    const containerStatusKey = `container_status_${challengeUuid}`;
    const containerInfoKey = `container_info_${challengeUuid}`;
    const containerCreatedKey = `container_created_${challengeUuid}`;
    let countdownInterval;
    let isRequestPending = false;
    function startCountdown(expirationTime) {
        if (countdownInterval) {
            clearInterval(countdownInterval);
        }

        var countdownElement = $('#countdown');
        countdownInterval = setInterval(function () {
            var now = new Date().getTime();
            var distance = expirationTime - now;

            if (distance < 0) {
                clearInterval(countdownInterval);
                countdownElement.text("容器已过期");
                localStorage.removeItem(containerStatusKey);
                localStorage.removeItem(containerInfoKey);
                localStorage.removeItem(containerCreatedKey);
                showCreateButton();
                return;
            }

            var hours = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
            var minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
            var seconds = Math.floor((distance % (1000 * 60)) / 1000);

            $('#hours-tens').text(Math.floor(hours / 10));
            $('#hours-ones').text(hours % 10);
            $('#minutes-tens').text(Math.floor(minutes / 10));
            $('#minutes-ones').text(minutes % 10);
            $('#seconds-tens').text(Math.floor(seconds / 10));
            $('#seconds-ones').text(seconds % 10);
        }, 1000);
    }

    function clearCountdown() {
        if (countdownInterval) {
            clearInterval(countdownInterval);
            countdownInterval = null;
        }
    }

    function updateContainerInfo(containerInfo) {
        
        $('#results').html(`
            <div class="alert alert-primary d-flex align-items-center" role="alert">
                <div class="containers-info flex-grow-1">
                    <div class="url-display">
                    容器 URL: 
                    ${containerInfo.container_urls.map((url, index) => {
                        // 从URL中提取端口号
                        const port = url.split(':').pop();
                        
                        return index === 0 
                            ? `<a href="${url}" target="_blank" class="container-link">
                                 ${url}
                               </a>`
                            : `<a href="${url}" target="_blank" class="container-link">
                                 ${port}
                               </a>`
                    }).join(' | ')}
                    </div>
                </div>
                <div class="countdown-wrapper d-flex align-items-center">
                    <i class="far fa-clock mr-2"></i>
                    <div class="countdown-container" id="countdown">
                    <div class="countdown-block">
                        <div class="countdown-digits">
                        <span id="hours-tens">0</span><span id="hours-ones">0</span>
                        </div>
                    </div>
                    <div class="countdown-block">
                        <div class="countdown-digits">
                        <span id="minutes-tens">0</span><span id="minutes-ones">0</span>
                        </div>
                    </div>
                    <div class="countdown-block">
                        <div class="countdown-digits">
                        <span id="seconds-tens">0</span><span id="seconds-ones">0</span>
                        </div>
                    </div>
                    </div>
                </div>
            </div>
        `).show();
        startCountdown(new Date(containerInfo.expires_at).getTime());
        showDestroyButton();
    }

    function showCreateButton() {
        $('#createContainerBtn').show();
        $('#destroyContainerBtn').hide();
        $('#results').hide();
    }

    function showDestroyButton() {
        $('#createContainerBtn').hide();
        $('#destroyContainerBtn').show();
    }

    function toggleButtonLoading(button, isLoading) {
        if (isLoading) {
            button.prop('disabled', true);
            button.html(`
                <div style="display: flex; align-items: center; justify-content: center;">
                <span class="spinner-border spinner-border-sm spinner-border-xs" role="status" aria-hidden="true" style="margin-right: 5px;"></span>
                <span>Loading...</span>
            </div>
            `);
        } else {
            button.prop('disabled', false);
            button.html(button.data('original-text'));
        }
    }

    function loadContainerStatus() {
        if (localStorage.getItem(containerCreatedKey) === 'true') {
            $.ajax({
                url: '/api/v1/check_container_status/',
                type: 'GET',
                data: { 
                    challenge_uuid: challengeUuid,
                },
                timeout: 20000,
                success: function(response) {
                    if (response.status === 'active') {
                        updateContainerInfo(response);
                    } else {
                        showCreateButton();
                        localStorage.removeItem(containerStatusKey);
                        localStorage.removeItem(containerInfoKey);
                        localStorage.removeItem(containerCreatedKey);
                    }
                },
                error: function() {
                    showCreateButton();
                    localStorage.removeItem(containerStatusKey);
                    localStorage.removeItem(containerInfoKey);
                    localStorage.removeItem(containerCreatedKey);
                }
            });
        } else {
            showCreateButton();
        }
    }

    function handleCreateContainer(e) {
        e.preventDefault();
        
        if (isRequestPending) return;
        
        var button = $(this);
        var csrf = button.data('csrf');
        var url = button.data('ajax-url');

        if (!url || !csrf) {
            console.error('Missing required data attributes');
            return;
        }

        button.data('original-text', button.html());
        toggleButtonLoading(button, true);
        isRequestPending = true;

        $.ajax({
            url: url,
            type: 'POST',
            data: {
                challenge_uuid: challengeUuid,
                csrfmiddlewaretoken: csrf
            },
            timeout: 300000,
            success: function (response) {
                localStorage.setItem(containerStatusKey, 'active');
                localStorage.setItem(containerInfoKey, JSON.stringify(response));
                localStorage.setItem(containerCreatedKey, 'true');
                updateContainerInfo(response);
            },
            error: function (xhr, status, error) {
                let errorMessage = "请求失败，请稍后重试";
                if (xhr.responseJSON && xhr.responseJSON.error) {
                    errorMessage = xhr.responseJSON.error;
                } else if (status === 'timeout') {
                    errorMessage = "请求超时，请稍后重试";
                }
                $('#results').html(`<div class="alert alert-danger f-14 text-center" role="alert">${errorMessage}</div>`).show();
            },
            complete: function () {
                toggleButtonLoading(button, false);
                isRequestPending = false;
            }
        });
    }

    function handleDestroyContainer(e) {
        e.preventDefault();
        
        if (isRequestPending) return;
        
        var button = $(this);
        var csrf = button.data('csrf');
        var url = button.data('ajax-url');

        if (!url || !csrf) {
            console.error('Missing required data attributes');
            return;
        }

        button.data('original-text', button.html());
        toggleButtonLoading(button, true);
        isRequestPending = true;

        $.ajax({
            url: url,
            type: 'POST',
            data: {
                challenge_uuid: challengeUuid,
                csrfmiddlewaretoken: csrf
            },
            timeout: 300000,
            success: function (response) {
                $('#results').html(`<div class="alert alert-primary" role="alert">容器已摧毁</div>`).show();
                localStorage.removeItem(containerStatusKey);
                localStorage.removeItem(containerInfoKey);
                localStorage.removeItem(containerCreatedKey);
                clearCountdown();
                showCreateButton();
            },
            error: function (xhr, status, error) {
                let errorMessage = "请求失败，请稍后重试";
                if (xhr.responseJSON && xhr.responseJSON.error) {
                    errorMessage = xhr.responseJSON.error;
                } else if (status === 'timeout') {
                    errorMessage = "请求超时，请稍后重试";
                }
                $('#results').html(`<div class="alert alert-danger f-14 text-center" role="alert">${errorMessage}</div>`).show();
            },
            complete: function () {
                toggleButtonLoading(button, false);
                isRequestPending = false;
            }
        });
    }

    $(document).on('click', '#createContainerBtn', handleCreateContainer);
    $(document).on('click', '#destroyContainerBtn', handleDestroyContainer);

    // 页面卸载前清理
    $(window).on('beforeunload', function() {
        clearCountdown();
    });

    loadContainerStatus();

});