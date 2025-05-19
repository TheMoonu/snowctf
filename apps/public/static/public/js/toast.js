/**
 * 自定义Toast提示框工具库
 * 提供简单易用的提示框功能，替代浏览器原生alert
 */

// 确保DOM加载完成后初始化Toast容器
document.addEventListener('DOMContentLoaded', function() {
    // 如果页面中没有toast容器，则创建一个
    if (!document.querySelector('.custom-toast-container')) {
        const toastContainer = document.createElement('div');
        toastContainer.className = 'custom-toast-container';
        toastContainer.style.position = 'fixed';
        toastContainer.style.top = '20px';
        toastContainer.style.right = '20px';
        toastContainer.style.zIndex = '9999';
        document.body.appendChild(toastContainer);
    }
});

/**
 * 显示Toast提示框
 * @param {string} message - 提示消息内容
 * @param {string} title - 提示框标题
 * @param {number} delay - 显示时间（毫秒）
 * @param {string} type - 提示类型（info, success, warning, danger）
 */
function showToast(message, title = "提示", delay = 3000, type = "info") {
    // 获取或创建toast容器
    let toastContainer = document.querySelector('.custom-toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.className = 'custom-toast-container';
        document.body.appendChild(toastContainer);
    }
    
    // 创建唯一ID
    const toastId = 'toast-' + Date.now();
    
    // 创建toast HTML
    const toastHtml = `
        <div id="${toastId}" class="custom-toast custom-toast-${type}" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="custom-toast-header ${type !== 'info' ? 'custom-bg-' + type : ''}">
                <strong class="custom-title">${title}</strong>
                <div class="custom-header-right">
                    <small class="custom-time">${new Date().toLocaleTimeString()}</small>
                    <button type="button" class="custom-close" onclick="handleCloseClick(this)">
                        <span aria-hidden="true">&times;</span>
                    </button>
                </div>
            </div>
            <div class="custom-toast-body">
                ${message}
            </div>
        </div>
    `;
    
    // 添加toast到容器
    toastContainer.insertAdjacentHTML('beforeend', toastHtml);
    
    // 获取刚刚创建的toast元素
    const toastElement = document.getElementById(toastId);
    
    // 确保元素已添加到DOM
    requestAnimationFrame(() => {
        requestAnimationFrame(() => {
            toastElement.classList.add('show');
        });
    });
    
    // 设置自动关闭
    if (delay > 0) {
        setTimeout(() => {
            closeToast(toastElement);
        }, delay);
    }
    
    return toastElement;
}

/**
 * 显示成功提示框
 * @param {string} message - 提示消息内容
 * @param {string} title - 提示框标题
 * @param {number} delay - 显示时间（毫秒）
 */
function showSuccessToast(message, title = "成功", delay = 3000) {
    return showToast(message, title, delay, "success");
}

/**
 * 显示警告提示框
 * @param {string} message - 提示消息内容
 * @param {string} title - 提示框标题
 * @param {number} delay - 显示时间（毫秒）
 */
function showWarningToast(message, title = "警告", delay = 4000) {
    return showToast(message, title, delay, "warning");
}

/**
 * 显示错误提示框
 * @param {string} message - 提示消息内容
 * @param {string} title - 提示框标题
 * @param {number} delay - 显示时间（毫秒）
 */
function showErrorToast(message, title = "错误", delay = 5000) {
    return showToast(message, title, delay, "danger");
}

/**
 * 显示信息提示框
 * @param {string} message - 提示消息内容
 * @param {string} title - 提示框标题
 * @param {number} delay - 显示时间（毫秒）
 */
function showInfoToast(message, title = "提示", delay = 3000) {
    return showToast(message, title, delay, "info");
}

/**
 * 替代原生alert的函数
 * @param {string} message - 提示消息内容
 */
function toast(message) {
    return showToast(message, "提示", 3000, "info");
}

// 添加关闭函数
function closeToast(element) {
    const toast = element.closest ? element.closest('.custom-toast') : element;
    if (!toast || toast.classList.contains('removing')) return;
    
    // 添加removing类触发动画
    toast.classList.add('removing');
    toast.classList.remove('show');
    
    // 等待动画完成后移除元素
    const handleTransitionEnd = (e) => {
        if (e.propertyName === 'transform') {
            toast.removeEventListener('transitionend', handleTransitionEnd);
            if (toast.parentNode) {
                toast.remove();
            }
        }
    };
    
    toast.addEventListener('transitionend', handleTransitionEnd);
}

// 优化关闭按钮点击处理
function handleCloseClick(button) {
    const toast = button.closest('.custom-toast');
    if (toast) {
        closeToast(toast);
    }
}