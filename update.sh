#!/bin/bash

# SecSnow网络安全综合学习平台 更新脚本
# 用途：更新 SecSnow Web 服务到新版本

# 设置颜色输出
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置变量
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${SCRIPT_DIR}"
BASE_DIR="${INSTALL_DIR}/base"
BACKUP_DIR="${INSTALL_DIR}/backups"

# 版本信息
VERSION="1.0.0"
UPDATE_DATE=$(date '+%Y-%m-%d %H:%M:%S')

# 显示步骤信息
show_step() {
    echo -e "${GREEN}[步骤] $1${NC}"
}

# 显示警告信息
show_warning() {
    echo -e "${YELLOW}[警告] $1${NC}"
}

# 显示错误信息
show_error() {
    echo -e "${RED}[错误] $1${NC}"
    exit 1
}

# 显示成功信息
show_success() {
    echo -e "${GREEN}[成功] $1${NC}"
}

# 显示信息
show_info() {
    echo -e "${BLUE}[信息] $1${NC}"
}

# 获取可用的 Docker Compose 命令
get_compose_command() {
    if docker compose version &> /dev/null 2>&1; then
        echo "docker compose"
    elif command -v docker-compose &> /dev/null; then
        echo "docker-compose"
    else
        echo ""
    fi
}

# 检查环境
check_environment() {
    show_step "检查更新环境..."
    
    # 检查是否在正确的目录
    if [ ! -f "${INSTALL_DIR}/docker-compose.yml" ]; then
        show_error "未找到 docker-compose.yml，请确保在正确的安装目录运行此脚本"
    fi
    
    # 检查 .env 文件
    if [ ! -f "${INSTALL_DIR}/.env" ]; then
        show_error "未找到 .env 配置文件，请先运行安装脚本"
    fi
    
    # 检查 Docker
    if ! command -v docker &> /dev/null; then
        show_error "Docker 未安装"
    fi
    
    # 检查 Docker 服务
    if ! docker info &> /dev/null 2>&1; then
        show_error "Docker 服务未运行，请先启动 Docker"
    fi
    
    # 检查 Docker Compose
    COMPOSE_CMD=$(get_compose_command)
    if [ -z "$COMPOSE_CMD" ]; then
        show_error "未找到 Docker Compose"
    fi
    
    show_success "环境检查通过"
    show_info "使用 Docker Compose 命令: $COMPOSE_CMD"
}

# 检查新镜像文件
check_new_image() {
    show_step "检查新版本镜像..."
    
    if [ ! -d "${BASE_DIR}" ]; then
        show_error "base 目录不存在: ${BASE_DIR}"
    fi
    
    cd "${BASE_DIR}" || show_error "无法进入 base 目录"
    
    # 查找新的 SecSnow 镜像文件
    NEW_IMAGE_FILE=""
    
    # 优先查找带版本号的镜像
    for file in secsnow*.tar; do
        if [ -f "$file" ]; then
            NEW_IMAGE_FILE="$file"
            break
        fi
    done
    
    if [ -z "$NEW_IMAGE_FILE" ]; then
        show_error "未在 ${BASE_DIR} 目录找到新的 SecSnow 镜像文件 (secsnow*.tar)"
    fi
    
    show_success "找到新镜像文件: $NEW_IMAGE_FILE"
    ls -lh "$NEW_IMAGE_FILE"
    
    export NEW_IMAGE_FILE
}

# 备份当前数据
backup_data() {
    show_step "备份当前数据..."
    
    # 创建备份目录
    BACKUP_TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
    CURRENT_BACKUP_DIR="${BACKUP_DIR}/${BACKUP_TIMESTAMP}"
    mkdir -p "${CURRENT_BACKUP_DIR}"
    
    cd "${INSTALL_DIR}" || show_error "无法进入安装目录"
    
    # 备份 .env 文件
    show_info "备份配置文件..."
    cp .env "${CURRENT_BACKUP_DIR}/.env.backup" 2>/dev/null || true
    cp .credentials "${CURRENT_BACKUP_DIR}/.credentials.backup" 2>/dev/null || true
    
    # 备份数据库（可选）
    show_info "备份数据库..."
    if docker ps | grep -q secsnow-postgres; then
        docker exec secsnow-postgres pg_dump -U secsnow secsnow > "${CURRENT_BACKUP_DIR}/database.sql" 2>/dev/null
        if [ $? -eq 0 ]; then
            show_success "数据库备份完成: ${CURRENT_BACKUP_DIR}/database.sql"
        else
            show_warning "数据库备份失败，继续更新..."
        fi
    else
        show_warning "PostgreSQL 容器未运行，跳过数据库备份"
    fi
    
    # 记录备份信息
    cat > "${CURRENT_BACKUP_DIR}/backup_info.txt" << EOF
备份时间: ${UPDATE_DATE}
备份目录: ${CURRENT_BACKUP_DIR}
更新前镜像: $(grep SECSNOW_IMAGE .env 2>/dev/null || echo "未知")
EOF
    
    show_success "备份完成: ${CURRENT_BACKUP_DIR}"
    export CURRENT_BACKUP_DIR
}

# 停止服务
stop_services() {
    show_step "停止当前服务..."
    
    cd "${INSTALL_DIR}" || show_error "无法进入安装目录"
    
    COMPOSE_CMD=$(get_compose_command)
    
    # 只停止 web 相关服务，保留数据库
    show_info "停止 Web 服务..."
    $COMPOSE_CMD stop web celery celery-beat 2>/dev/null || true
    
    # 移除旧容器（保留数据卷）
    show_info "移除旧容器..."
    $COMPOSE_CMD rm -f web celery celery-beat 2>/dev/null || true
    
    show_success "服务已停止"
}

# 加载新镜像
load_new_image() {
    show_step "加载新版本镜像..."
    
    cd "${BASE_DIR}" || show_error "无法进入 base 目录"
    
    # 记录旧镜像信息
    OLD_IMAGE=$(docker images | grep secsnow | head -1 | awk '{print $1":"$2}')
    show_info "当前镜像: ${OLD_IMAGE:-无}"
    
    # 加载新镜像
    show_info "加载新镜像: ${NEW_IMAGE_FILE}..."
    LOAD_OUTPUT=$(docker load -i "${NEW_IMAGE_FILE}" 2>&1)
    
    if [ $? -eq 0 ]; then
        # 提取新镜像名称
        NEW_IMAGE_NAME=$(echo "$LOAD_OUTPUT" | grep -oP 'Loaded image: \K.*' || echo "")
        if [ -z "$NEW_IMAGE_NAME" ]; then
            NEW_IMAGE_NAME=$(echo "$LOAD_OUTPUT" | grep -oP 'Loaded image ID: \K.*' || echo "secsnow:latest")
        fi
        show_success "新镜像加载成功: $NEW_IMAGE_NAME"
    else
        show_error "镜像加载失败: $LOAD_OUTPUT"
    fi
    
    # 显示镜像列表
    show_info "当前 SecSnow 镜像列表："
    docker images | grep -E "secsnow|REPOSITORY" || true
    
    export NEW_IMAGE_NAME
}

# 更新配置文件
update_config() {
    show_step "更新配置文件..."
    
    cd "${INSTALL_DIR}" || show_error "无法进入安装目录"
    
    if [ -n "$NEW_IMAGE_NAME" ]; then
        # 更新 .env 文件中的镜像版本
        if grep -q "SECSNOW_IMAGE=" .env; then
            # 备份当前配置
            cp .env .env.pre_update
            
            # 更新镜像配置
            sed -i "s|^SECSNOW_IMAGE=.*|SECSNOW_IMAGE=${NEW_IMAGE_NAME}|" .env
            
            show_success "已更新 SECSNOW_IMAGE 为: ${NEW_IMAGE_NAME}"
        else
            # 如果没有该配置项，添加它
            echo "" >> .env
            echo "# 更新于 ${UPDATE_DATE}" >> .env
            echo "SECSNOW_IMAGE=${NEW_IMAGE_NAME}" >> .env
            show_info "已添加 SECSNOW_IMAGE 配置"
        fi
    fi
    
    show_success "配置文件更新完成"
}

# 启动服务
start_services() {
    show_step "启动更新后的服务..."
    
    cd "${INSTALL_DIR}" || show_error "无法进入安装目录"
    
    COMPOSE_CMD=$(get_compose_command)
    
    # 拉起所有服务
    show_info "启动所有服务..."
    if $COMPOSE_CMD up -d; then
        show_success "服务启动成功"
    else
        show_error "服务启动失败，请检查日志"
    fi
    
    # 等待服务就绪
    show_info "等待服务完全启动..."
    sleep 10
    
    # 显示服务状态
    show_info "服务状态："
    $COMPOSE_CMD ps
}

# 执行数据库迁移
run_migrations() {
    show_step "执行数据库迁移..."
    
    # 等待 Web 服务就绪
    show_info "等待 Web 服务就绪..."
    sleep 5
    
    # 检查容器是否运行
    if ! docker ps | grep -q secsnow-web; then
        show_error "Web 容器未运行，无法执行迁移"
    fi
    
    # 执行迁移
    show_info "检查并应用数据库迁移..."
    docker exec secsnow-web python manage.py migrate --noinput
    
    if [ $? -eq 0 ]; then
        show_success "数据库迁移完成"
    else
        show_warning "数据库迁移可能有问题，请检查日志"
    fi
    
    # 收集静态文件
    show_info "收集静态文件..."
    docker exec secsnow-web python manage.py collectstatic --noinput 2>/dev/null
    
    if [ $? -eq 0 ]; then
        show_success "静态文件收集完成"
    else
        show_warning "静态文件收集可能有问题"
    fi
}

# 验证更新
verify_update() {
    show_step "验证更新结果..."
    
    # 检查 Web 服务健康状态
    show_info "检查服务健康状态..."
    
    # 等待服务完全启动
    sleep 5
    
    # 检查容器状态
    WEB_STATUS=$(docker inspect -f '{{.State.Status}}' secsnow-web 2>/dev/null || echo "未知")
    
    if [ "$WEB_STATUS" == "running" ]; then
        show_success "Web 服务运行正常"
    else
        show_warning "Web 服务状态: $WEB_STATUS"
    fi
    
    # 尝试访问健康检查端点
    show_info "测试服务响应..."
    sleep 3
    
    # 检查是否能访问
    if curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:80 2>/dev/null | grep -qE "200|301|302"; then
        show_success "服务响应正常"
    else
        show_warning "服务可能尚未完全就绪，请稍后手动验证"
    fi
    
    # 显示当前运行的镜像版本
    show_info "当前运行的镜像："
    docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}" | grep -E "secsnow|NAMES"
}

# 清理旧镜像（可选）
cleanup_old_images() {
    show_step "清理旧镜像（可选）..."
    
    # 显示所有 SecSnow 相关镜像
    show_info "当前 SecSnow 镜像列表："
    docker images | grep -E "secsnow|REPOSITORY"
    
    echo ""
    read -p "是否删除旧版本镜像以释放空间? (y/n): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # 获取当前使用的镜像
        CURRENT_IMAGE=$(docker inspect -f '{{.Config.Image}}' secsnow-web 2>/dev/null || echo "")
        
        # 删除未使用的 SecSnow 镜像
        show_info "清理未使用的镜像..."
        docker images | grep secsnow | grep -v "$CURRENT_IMAGE" | awk '{print $3}' | xargs -r docker rmi 2>/dev/null || true
        
        # 清理悬空镜像
        docker image prune -f 2>/dev/null || true
        
        show_success "旧镜像清理完成"
    else
        show_info "跳过清理旧镜像"
    fi
}

# 显示更新完成信息
show_completion() {
    echo ""
    echo "========================================="
    echo -e "${GREEN}🎉 更新完成！${NC}"
    echo "========================================="
    echo ""
    echo -e "${BLUE}更新信息:${NC}"
    echo "  更新时间: ${UPDATE_DATE}"
    echo "  新镜像: ${NEW_IMAGE_NAME:-未知}"
    echo "  备份目录: ${CURRENT_BACKUP_DIR:-未备份}"
    echo ""
    
    COMPOSE_CMD=$(get_compose_command)
    
    echo -e "${BLUE}常用命令:${NC}"
    echo "  查看服务状态:"
    echo "    cd ${INSTALL_DIR} && $COMPOSE_CMD ps"
    echo ""
    echo "  查看 Web 日志:"
    echo "    docker logs -f secsnow-web"
    echo ""
    echo "  回滚到旧版本（如果需要）:"
    echo "    1. 停止服务: $COMPOSE_CMD down"
    echo "    2. 恢复配置: cp ${CURRENT_BACKUP_DIR}/.env.backup .env"
    echo "    3. 重新加载旧镜像"
    echo "    4. 启动服务: $COMPOSE_CMD up -d"
    echo ""
    echo -e "${YELLOW}提示:${NC}"
    echo "  1. 如遇问题，可查看日志: docker logs secsnow-web"
    echo "  2. 备份文件保存在: ${BACKUP_DIR}"
    echo "  3. 建议测试主要功能是否正常"
    echo "========================================="
}

# 从 Docker 仓库拉取镜像
pull_image_from_registry() {
    show_step "从 Docker 仓库拉取镜像..."
    
    if [ -z "$REGISTRY_IMAGE" ]; then
        show_error "未指定要拉取的镜像名称，请使用 --image 参数"
    fi
    
    # 记录旧镜像信息
    OLD_IMAGE=$(docker images | grep secsnow | head -1 | awk '{print $1":"$2}')
    show_info "当前镜像: ${OLD_IMAGE:-无}"
    
    # 拉取新镜像
    show_info "正在拉取镜像: ${REGISTRY_IMAGE}..."
    if docker pull "${REGISTRY_IMAGE}"; then
        show_success "镜像拉取成功: ${REGISTRY_IMAGE}"
        NEW_IMAGE_NAME="${REGISTRY_IMAGE}"
    else
        show_error "镜像拉取失败，请检查镜像名称和网络连接"
    fi
    
    # 显示镜像列表
    show_info "当前 SecSnow 镜像列表："
    docker images | grep -E "secsnow|REPOSITORY" || true
    
    export NEW_IMAGE_NAME
}

# 显示帮助信息
show_help() {
    echo ""
    echo "SecSnow 更新脚本 v${VERSION}"
    echo ""
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  -h, --help              显示此帮助信息"
    echo "  -y, --yes               跳过确认提示，直接更新"
    echo "  --no-backup             跳过备份步骤"
    echo "  --no-migrate            跳过数据库迁移"
    echo "  --cleanup               更新后自动清理旧镜像"
    echo "  --pull                  从 Docker 仓库拉取镜像（而非本地 tar 文件）"
    echo "  --image <镜像名称>      指定要拉取的镜像（配合 --pull 使用）"
    echo "                          格式: registry/image:tag"
    echo ""
    echo "示例:"
    echo "  $0                      交互式更新（使用本地 tar 文件）"
    echo "  $0 -y                   自动确认更新（使用本地 tar 文件）"
    echo "  $0 --cleanup            更新并清理旧镜像"
    echo "  $0 --pull --image secsnow/web:v2.0.0"
    echo "                          从仓库拉取指定镜像"
    echo "  $0 --pull --image registry.example.com/secsnow:latest -y"
    echo "                          从私有仓库拉取镜像并自动确认"
    echo ""
    echo "更新模式:"
    echo "  1. 本地模式（默认）: 从 ${BASE_DIR} 目录加载 secsnow*.tar 文件"
    echo "  2. 仓库模式（--pull）: 从 Docker 仓库拉取指定镜像"
    echo ""
    echo "更新前请确保:"
    echo "  - 本地模式: 新的镜像文件 (secsnow*.tar) 已放入 ${BASE_DIR} 目录"
    echo "  - 仓库模式: 有网络连接且可以访问 Docker 仓库"
    echo "  - 当前服务正在运行"
    echo "  - 有足够的磁盘空间用于备份"
    echo ""
}

# 主函数
main() {
    # 解析参数
    SKIP_CONFIRM=false
    SKIP_BACKUP=false
    SKIP_MIGRATE=false
    AUTO_CLEANUP=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -y|--yes)
                SKIP_CONFIRM=true
                shift
                ;;
            --no-backup)
                SKIP_BACKUP=true
                shift
                ;;
            --no-migrate)
                SKIP_MIGRATE=true
                shift
                ;;
            --cleanup)
                AUTO_CLEANUP=true
                shift
                ;;
            *)
                show_warning "未知参数: $1"
                shift
                ;;
        esac
    done
    
    echo ""
    echo "========================================="
    echo -e "${GREEN}SecSnow 服务更新脚本 v${VERSION}${NC}"
    echo "========================================="
    echo ""
    
    # 显示配置信息
    echo -e "${BLUE}更新配置:${NC}"
    echo "  安装目录: ${INSTALL_DIR}"
    echo "  镜像目录: ${BASE_DIR}"
    echo "  备份目录: ${BACKUP_DIR}"
    echo ""
    
    # 确认继续
    if [ "$SKIP_CONFIRM" = false ]; then
        read -p "是否继续更新? (y/n): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            show_warning "更新已取消"
            exit 0
        fi
    fi
    
    echo ""
    
    # 执行更新步骤
    check_environment
    check_new_image
    
    if [ "$SKIP_BACKUP" = false ]; then
        backup_data
    else
        show_info "跳过备份步骤"
    fi
    
    stop_services
    load_new_image
    update_config
    start_services
    
    if [ "$SKIP_MIGRATE" = false ]; then
        run_migrations
    else
        show_info "跳过数据库迁移"
    fi
    
    verify_update
    
    if [ "$AUTO_CLEANUP" = true ]; then
        # 自动清理，不询问
        show_info "自动清理旧镜像..."
        docker image prune -f 2>/dev/null || true
    else
        cleanup_old_images
    fi
    
    show_completion
}

# 执行主函数
main "$@"

