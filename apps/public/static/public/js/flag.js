$(document).ready(function () {
    var $submitFlag = $('#submit-flag');
    var $flagInput = $('#flag-input');
    var $result = $('#result');
    var challengeUuid = $submitFlag.data('challenge-uuid');
    var verifyFlagUrl = $submitFlag.data('verify-url');
    var csrfToken = $submitFlag.data('csrf');
    var submitTimeout = null;

    function disableSubmit(duration) {
        $submitFlag.prop('disabled', true);
        $submitFlag.find('.button-text').addClass('d-none');
        $submitFlag.find('.spinner-border').removeClass('d-none');
        clearTimeout(submitTimeout);
        submitTimeout = setTimeout(function() {
            $submitFlag.prop('disabled', false);
            $submitFlag.find('.button-text').removeClass('d-none');
            $submitFlag.find('.spinner-border').addClass('d-none');
        }, duration);
    }

    function showResult(message, isSuccess) {
        var alertClass = isSuccess ? 'alert-success' : 'alert-danger';
        $result.html(`<div class="alert ${alertClass} f-14 text-center" role="alert">${message}</div>`);
    }

    $submitFlag.click(function () {
        if ($submitFlag.prop('disabled')) {
            return;
        }

        var flag = $flagInput.val().trim();
        if (!flag) {
            showResult('FLAG不能为空', false);
            return;
        }

        disableSubmit(5000); // 禁用按钮 5 秒

        $.ajax({
            url: verifyFlagUrl,
            type: "POST",
            data: {
                challenge_uuid: challengeUuid,
                flag: flag
            },
            headers: {
                "X-CSRFToken": csrfToken
            },
            dataType: 'json',
            success: function (data) {
                showResult(data.message, data.status === 'success');
                if (data.status === 'success') {
                    $flagInput.val(''); // 清空输入框
                }
            },
            error: function (jqXHR, textStatus, errorThrown) {
                var errorMessage = '提交过程中发生错误，请稍后再试。';
                try {
                    var response = JSON.parse(jqXHR.responseText);
                    if (response.message) {
                        errorMessage = response.message;
                    }
                } catch (e) {
                    console.error("Error parsing JSON response: ", e);
                }
                showResult(errorMessage, false);
            },
            complete: function() {
                // 如果需要，可以在这里添加额外的逻辑
            }
        });
    });

    // 允许用户按回车键提交
    $flagInput.keypress(function(e) {
        if (e.which == 13) { // 回车键的键码是 13
            $submitFlag.click();
            return false; // 防止表单提交
        }
    });
});