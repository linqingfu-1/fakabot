#!/usr/bin/env bash
# ============================================================================
# fakabot 多机器人 USDT 扫链集群 一键部署脚本
# 对应部署文档 deploy/MULTI_BOT_USDT_DEPLOYMENT.md 第 0 节全流程（0.1 ~ 0.16）
#
# 用法（在 Ubuntu 服务器上以 root 执行）：
#   ./deploy_multi_bot.sh init      # 生成 deploy.env 模板，填写后继续
#   ./deploy_multi_bot.sh deploy    # 一键完成：拉代码→生成配置→改compose→构建→启动→验证
#   ./deploy_multi_bot.sh nginx-setup # 自动安装 Nginx+申请 HTTPS 证书+配置 6 组转发
#   ./deploy_multi_bot.sh verify    # 验证容器、健康检查、扫链日志
#   ./deploy_multi_bot.sh update    # 更新代码并重建（保留 config.json/data/compose）
#   ./deploy_multi_bot.sh backup    # 备份 6 个业务库和共享扫链库
#   ./deploy_multi_bot.sh nginx     # 仅生成 Nginx location 片段（手动模式）
#   ./deploy_multi_bot.sh status    # 查看容器状态
#   ./deploy_multi_bot.sh logs <bot01|...|scanner> [--follow]
#   ./deploy_multi_bot.sh restart <bot01|...|scanner|all>
#   ./deploy_multi_bot.sh stop    <bot01|...|scanner|all>
#
# 说明：
#   - 默认集群目录 /opt/fakabot-cluster，可用环境变量 CLUSTER_DIR 覆盖。
#   - deploy 会重置各目录的 config.json 和 docker-compose.yml（按模板重新生成），
#     只用于从零部署/重新初始化；日常更新代码请用 update（会保留两者）。
# ============================================================================
set -euo pipefail

CLUSTER_DIR="${CLUSTER_DIR:-/opt/fakabot-cluster}"
ENV_FILE="$CLUSTER_DIR/deploy.env"
BACKUP_DIR="${BACKUP_DIR:-/opt/fakabot-backup}"

BOTS=(bot01 bot02 bot03 bot04 bot05 bot06)
APP_PORTS=(58201 58202 58203 58204 58205 58206)
EXTRA_PORTS=(58301 58302 58303 58304 58305 58306)

die() { echo "❌ $*" >&2; exit 1; }
info() { echo "===> $*"; }

usage() {
    sed -n '2,17p' "$0" | sed 's/^# \{0,1\}//'
    exit 0
}

# ---------------------------------------------------------------------------
# 0.1 变量加载与校验
# ---------------------------------------------------------------------------
load_env() {
    [[ -f "$ENV_FILE" ]] || die "找不到 $ENV_FILE，请先执行: $0 init 并填写变量"
    set -a
    # shellcheck disable=SC1090
    . "$ENV_FILE"
    set +a

    # 可选参数默认值（env 未定义时才生效）
    : "${KAVIP_ENABLED:=true}"
    : "${KAVIP_MERCHANT_ID:=1023}"
    : "${KAVIP_KEY:=76F67wdDD7p56l7g1F66wFTRLv7pd5rv}"
    : "${KAVIP_GATEWAY:=https://kavip.biz/submit.php}"
    : "${KAVIP_API_GATEWAY:=https://kavip.biz/mapi.php}"
    : "${USDT_CNY_RATE:=7.20}"
    : "${USDT_MIN_AMOUNT:=1.00}"

    # 必填校验
    [[ -n "${REPO_URL:-}" ]] || die "deploy.env 的 REPO_URL 未填写"
    [[ "${ADMIN_ID:-}" =~ ^[0-9]+$ ]] || die "deploy.env 的 ADMIN_ID 必须是数字"
    for i in 1 2 3 4 5 6; do
        local tv="BOT0${i}_TOKEN" dv="BOT0${i}_DOMAIN"
        local token="${!tv:-}" domain="${!dv:-}"
        [[ -n "$token" && "$token" != *"的TelegramToken"* ]] || die "deploy.env 的 $tv 未填写"
        [[ -n "$domain" ]] || die "deploy.env 的 $dv 未填写"
    done
    [[ -n "${TRONGRID_KEY_1:-}" && "$TRONGRID_KEY_1" != *"你的TronGridKey"* ]] \
        || die "deploy.env 的 TRONGRID_KEY_1 未填写"
}

# ---------------------------------------------------------------------------
# init：生成 deploy.env 模板
# ---------------------------------------------------------------------------
cmd_init() {
    if [[ -f "$ENV_FILE" ]]; then
        info "$ENV_FILE 已存在，如需重新生成请先删除它"
        return 0
    fi
    mkdir -p "$CLUSTER_DIR"
    cat > "$ENV_FILE" <<'EOF'
# ============ 必填 ============

# fakabot 仓库地址（git clone 使用，默认官方仓库，可用自己的 fork 覆盖）
REPO_URL="https://github.com/linqingfu-1/fakabot.git"

# Telegram 管理员数字 ID
ADMIN_ID="8755978774"

# TronGrid API key（第 1 个必填，第 2/3 个可选，用于 429 限流切换）
TRONGRID_KEY_1="你的TronGridKey1"
TRONGRID_KEY_2="你的TronGridKey2"
TRONGRID_KEY_3="你的TronGridKey3"

# 6 个机器人的 Telegram Bot Token（每个必须不同）
BOT01_TOKEN="bot01的TelegramToken"
BOT02_TOKEN="bot02的TelegramToken"
BOT03_TOKEN="bot03的TelegramToken"
BOT04_TOKEN="bot04的TelegramToken"
BOT05_TOKEN="bot05的TelegramToken"
BOT06_TOKEN="bot06的TelegramToken"

# 6 个机器人的对外域名（Nginx 按路径区分）
BOT01_DOMAIN="https://pay.unishopasa.cn/bot11"
BOT02_DOMAIN="https://pay.unishopasa.cn/bot12"
BOT03_DOMAIN="https://pay.unishopasa.cn/bot13"
BOT04_DOMAIN="https://pay.unishopasa.cn/bot14"
BOT05_DOMAIN="https://pay.unishopasa.cn/bot15"
BOT06_DOMAIN="https://pay.unishopasa.cn/bot16"

# ============ 可选 ============

# KAVIP 支付宝商户参数（也可在机器人管理后台配置）
KAVIP_ENABLED="true"
KAVIP_MERCHANT_ID="1023"
KAVIP_KEY="76F67wdDD7p56l7g1F66wFTRLv7pd5rv"
KAVIP_GATEWAY="https://kavip.biz/submit.php"
KAVIP_API_GATEWAY="https://kavip.biz/mapi.php"

# USDT 汇率与最小支付金额兜底（后台未设置时生效，也可在管理后台配置）
USDT_CNY_RATE="7.20"
USDT_MIN_AMOUNT="1.00"

# Let's Encrypt 证书申请邮箱（nginx-setup 自动申请证书时使用，可选）
CERTBOT_EMAIL="1459684961@qq.com"
EOF
    echo "✅ 已生成 $ENV_FILE"
    echo "   请编辑该文件填写真实值，然后执行: $0 deploy"
}

# ---------------------------------------------------------------------------
# 0.2 / 0.3 拉取源码、创建目录、复制项目
# ---------------------------------------------------------------------------
cmd_prepare() {
    load_env
    info "拉取/更新源码"
    mkdir -p "$CLUSTER_DIR"
    if [[ -d "$CLUSTER_DIR/source/.git" ]]; then
        (cd "$CLUSTER_DIR/source" && git pull --ff-only)
    else
        git clone "$REPO_URL" "$CLUSTER_DIR/source"
    fi

    info "创建共享目录和 6 个机器人数据目录"
    mkdir -p "$CLUSTER_DIR/shared" "$CLUSTER_DIR/scanner"
    chmod 755 "$CLUSTER_DIR/shared"
    for bot in "${BOTS[@]}"; do
        mkdir -p "$CLUSTER_DIR/$bot/data"
    done

    info "复制项目到 scanner 和各机器人目录（会重置 compose 和 config）"
    rm -rf "$CLUSTER_DIR/scanner/fakabot"
    cp -a "$CLUSTER_DIR/source" "$CLUSTER_DIR/scanner/fakabot"
    for bot in "${BOTS[@]}"; do
        rm -rf "$CLUSTER_DIR/$bot/fakabot"
        cp -a "$CLUSTER_DIR/source" "$CLUSTER_DIR/$bot/fakabot"
    done
    echo "✅ prepare 完成"
}

# ---------------------------------------------------------------------------
# 0.4 / 0.5 生成 scanner 与 6 个机器人的 config.json
# ---------------------------------------------------------------------------
gen_scanner_config() {
    ADMIN_ID_NUM="$ADMIN_ID" \
    TRONGRID_KEY_1="${TRONGRID_KEY_1:-}" \
    TRONGRID_KEY_2="${TRONGRID_KEY_2:-}" \
    TRONGRID_KEY_3="${TRONGRID_KEY_3:-}" \
    python3 - "$CLUSTER_DIR/scanner/fakabot/config.json" <<'PY'
import json, os, sys

keys = [
    k for k in (
        os.environ.get("TRONGRID_KEY_1", ""),
        os.environ.get("TRONGRID_KEY_2", ""),
        os.environ.get("TRONGRID_KEY_3", ""),
    ) if k
]
if not keys:
    raise SystemExit("没有可用的 TronGrid API key")

cfg = {
    "BOT_TOKEN": "SCANNER_ONLY_DO_NOT_RUN_BOT",
    "ADMIN_ID": int(os.environ["ADMIN_ID_NUM"]),
    "DOMAIN": "https://scanner.local",
    "ORDER_TIMEOUT_SECONDS": 3600,
    "PAYMENTS": {
        "usdt_trc20_direct": {
            "name": "USDT(TRC20直付)",
            "enabled": False,
            "priority": 20,
            "tron_api_key": keys[0],
            "timeout_seconds": 3600,
            "scan_interval_seconds": 10,
            "confirmations": 2,
            "max_blocks_per_scan": 5,
            "start_block": "",
        }
    },
    "USDT_SCAN": {
        "mode": "shared_scanner",
        "shared_store": "/shared/usdt_chain.db",
        "scan_interval_seconds": 10,
        "retention_hours": 24,
        "cleanup_interval_hours": 24,
        "vacuum_after_cleanup": True,
        "vacuum_min_deleted": 1000,
        "confirmations": 2,
        "max_blocks_per_scan": 5,
        "tron_api_keys": keys,
    },
    "START": {
        "cover_url": "",
        "title": "Scanner",
        "intro": "Shared USDT scanner",
        "title_en": "Scanner",
        "intro_en": "Shared USDT scanner",
    },
    "SHOW_QR": True,
    "PRODUCTS": [],
}
with open(sys.argv[1], "w", encoding="utf-8") as f:
    json.dump(cfg, f, ensure_ascii=False, indent=2)
    f.write("\n")
print(f"✅ 已生成 {sys.argv[1]}")
PY
}

gen_bot_config() {
    local bot="$1" token="$2" domain="$3"
    BOT_TOKEN="$token" BOT_DOMAIN="$domain" ADMIN_ID_NUM="$ADMIN_ID" \
    KAVIP_ENABLED="$KAVIP_ENABLED" \
    KAVIP_MERCHANT_ID="$KAVIP_MERCHANT_ID" KAVIP_KEY="$KAVIP_KEY" \
    KAVIP_GATEWAY="$KAVIP_GATEWAY" KAVIP_API_GATEWAY="$KAVIP_API_GATEWAY" \
    USDT_CNY_RATE="$USDT_CNY_RATE" USDT_MIN_AMOUNT="$USDT_MIN_AMOUNT" \
    python3 - "$CLUSTER_DIR/$bot/fakabot/config.json" <<'PY'
import json, os, sys

cfg = {
    "BOT_TOKEN": os.environ["BOT_TOKEN"],
    "ADMIN_ID": int(os.environ["ADMIN_ID_NUM"]),
    "DOMAIN": os.environ["BOT_DOMAIN"],
    "ORDER_TIMEOUT_SECONDS": 3600,
    "PAYMENTS": {
        "kavip_alipay": {
            "name": "支付宝",
            "enabled": os.environ.get("KAVIP_ENABLED", "true") == "true",
            "priority": 10,
            "merchant_id": os.environ["KAVIP_MERCHANT_ID"],
            "gateway": os.environ["KAVIP_GATEWAY"],
            "api_gateway": os.environ["KAVIP_API_GATEWAY"],
            "key": os.environ["KAVIP_KEY"],
            "type": "alipay",
            "route": "/pay/kavip",
        },
        "usdt_trc20_direct": {
            "name": "USDT(TRC20直付)",
            "enabled": True,
            "priority": 20,
            "timeout_seconds": 3600,
            "cny_per_usdt": os.environ.get("USDT_CNY_RATE", "7.20"),
            "min_usdt_amount": os.environ.get("USDT_MIN_AMOUNT", "1.00"),
        },
    },
    "USDT_SCAN": {
        "mode": "match_only",
        "shared_store": "/shared/usdt_chain.db",
        "scan_interval_seconds": 10,
    },
    "START": {
        "cover_url": "https://img.example/start-cover.jpg",
        "title": "欢迎选购",
        "intro": "这里是商店简介，可在后台或配置中调整。",
        "title_en": "Welcome",
        "intro_en": "Welcome.",
    },
    "SHOW_QR": True,
    "PRODUCTS": [
        {
            "name": "VIP课程",
            "cover_url": "https://img.example/cover.jpg",
            "description": "商品简介",
            "image_url": "https://img.example/detail.jpg",
            "full_description": "商品详情",
            "price": 99.9,
            "tg_group_id": "-1001234567890",
            "deliver_type": "join_group",
        }
    ],
}
with open(sys.argv[1], "w", encoding="utf-8") as f:
    json.dump(cfg, f, ensure_ascii=False, indent=2)
    f.write("\n")
print(f"✅ 已生成 {sys.argv[1]}")
PY
}

cmd_gen_configs() {
    load_env
    info "生成共享扫链服务配置（scanner/fakabot/config.json）"
    gen_scanner_config
    info "生成 6 个业务机器人配置"
    local i=1
    for bot in "${BOTS[@]}"; do
        local tv="BOT0${i}_TOKEN" dv="BOT0${i}_DOMAIN"
        gen_bot_config "$bot" "${!tv}" "${!dv}"
        i=$((i + 1))
    done
    echo "✅ 全部 config.json 生成完毕"
}

# ---------------------------------------------------------------------------
# 0.6 / 0.7 修改各目录 docker-compose.yml
# ---------------------------------------------------------------------------
patch_bot_compose() {
    local bot="$1" app_port="$2" extra_port="$3"
    local compose="$CLUSTER_DIR/$bot/fakabot/docker-compose.yml"
    sed -i "s/container_name: fakabot-redis/container_name: fakabot-${bot}-redis/g" "$compose"
    sed -i "s/container_name: fakabot-usdt-scanner/container_name: fakabot-${bot}-usdt-scanner/g" "$compose"
    sed -i "s/container_name: fakabot\$/container_name: fakabot-${bot}/g" "$compose"
    sed -i "s/fakabot_network/fakabot_${bot}_network/g" "$compose"
    sed -i "s/redis_data:/redis_data_${bot}:/g" "$compose"
    sed -i "s#- ./data:/app/data#- $CLUSTER_DIR/${bot}/data:/app/data#g" "$compose"
    sed -i "s#- usdt_chain_data:/shared#- $CLUSTER_DIR/shared:/shared#g" "$compose"
    sed -i "s#127.0.0.1:58001:58001#127.0.0.1:${app_port}:58001#g" "$compose"
    sed -i "s#127.0.0.1:58002:58002#127.0.0.1:${extra_port}:58002#g" "$compose"

    grep -q "container_name: fakabot-${bot}\$" "$compose" || die "${bot} compose 容器名修改失败"
    grep -q "127.0.0.1:${app_port}:58001" "$compose" || die "${bot} compose 端口修改失败"
    grep -q "$CLUSTER_DIR/shared:/shared" "$compose" || die "${bot} compose 共享挂载修改失败"
    echo "✅ ${bot} compose 已修改"
}

patch_scanner_compose() {
    local compose="$CLUSTER_DIR/scanner/fakabot/docker-compose.yml"
    sed -i 's/container_name: fakabot-redis/container_name: fakabot-scanner-redis/g' "$compose"
    sed -i 's/container_name: fakabot$/container_name: fakabot-scanner-bot-disabled/g' "$compose"
    sed -i 's/fakabot_network/fakabot_scanner_network/g' "$compose"
    sed -i 's/redis_data:/redis_data_scanner:/g' "$compose"
    sed -i "s#- usdt_chain_data:/shared#- $CLUSTER_DIR/shared:/shared#g" "$compose"

    grep -q "$CLUSTER_DIR/shared:/shared" "$compose" || die "scanner compose 共享挂载修改失败"
    echo "✅ scanner compose 已修改"
}

cmd_patch_compose() {
    load_env
    info "修改 scanner 的 docker-compose.yml"
    patch_scanner_compose
    info "修改 6 个机器人的 docker-compose.yml"
    local i=1
    for bot in "${BOTS[@]}"; do
        patch_bot_compose "$bot" "${APP_PORTS[$((i - 1))]}" "${EXTRA_PORTS[$((i - 1))]}"
        i=$((i + 1))
    done
}

# ---------------------------------------------------------------------------
# 0.8 校验 compose 并构建镜像
# ---------------------------------------------------------------------------
cmd_build() {
    load_env
    info "校验 scanner compose 配置"
    (cd "$CLUSTER_DIR/scanner/fakabot" && docker compose --profile multi-bot config >/dev/null)
    echo "✅ scanner compose ok"
    info "校验 6 个机器人 compose 配置"
    for bot in "${BOTS[@]}"; do
        (cd "$CLUSTER_DIR/$bot/fakabot" && docker compose config >/dev/null)
        echo "✅ ${bot} compose ok"
    done

    info "构建共享扫链服务镜像"
    (cd "$CLUSTER_DIR/scanner/fakabot" && docker compose --profile multi-bot build usdt_scanner)
    info "构建 6 个机器人镜像"
    for bot in "${BOTS[@]}"; do
        (cd "$CLUSTER_DIR/$bot/fakabot" && docker compose build sp_shop_bot)
    done
    echo "✅ 镜像构建完成"
}

# ---------------------------------------------------------------------------
# 0.9 / 0.10 启动服务
# ---------------------------------------------------------------------------
cmd_start() {
    load_env
    info "启动共享扫链服务"
    (cd "$CLUSTER_DIR/scanner/fakabot" && docker compose --profile multi-bot up -d usdt_scanner)
    info "启动 6 个业务机器人"
    for bot in "${BOTS[@]}"; do
        (cd "$CLUSTER_DIR/$bot/fakabot" && docker compose up -d redis sp_shop_bot)
    done
    echo "✅ 启动完成"
    cmd_verify
}

# ---------------------------------------------------------------------------
# 验证部署（0.10 / 0.13 / 0.14 摘要）
# ---------------------------------------------------------------------------
cmd_verify() {
    info "容器状态"
    docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | grep -E 'NAMES|fakabot' || true

    echo ""
    info "健康检查"
    local i=1
    local all_ok=1
    for bot in "${BOTS[@]}"; do
        local port="${APP_PORTS[$((i - 1))]}"
        if curl -fsS --max-time 5 "http://127.0.0.1:${port}/health" >/dev/null 2>&1; then
            echo "✅ ${bot} http://127.0.0.1:${port}/health ok"
        else
            echo "❌ ${bot} http://127.0.0.1:${port}/health 失败"
            all_ok=0
        fi
        i=$((i + 1))
    done

    echo ""
    info "共享扫链服务最近日志"
    docker logs --tail 20 fakabot-usdt-scanner 2>&1 || true

    echo ""
    info "共享扫链库"
    ls -lh "$CLUSTER_DIR/shared" 2>/dev/null || true

    if [[ "$all_ok" == "1" ]]; then
        echo ""
        echo "✅ 验证通过。剩余人工步骤："
        echo "   1. 执行 $0 nginx-setup 自动完成 Nginx 安装、证书申请与转发配置"
        echo "   2. Telegram 中每个机器人 /start、/admin 初始化后台"
        echo "   3. 后台配置 USDT 收款地址、汇率、最小金额并开启 USDT(TRC20直付)"
    fi
}

# ---------------------------------------------------------------------------
# 0.16 更新代码并重建（保留 config.json / data / docker-compose.yml）
# ---------------------------------------------------------------------------
cmd_update() {
    load_env
    command -v rsync >/dev/null 2>&1 || apt-get install -y rsync
    command -v rsync >/dev/null 2>&1 || die "rsync 安装失败"

    info "拉取最新源码"
    (cd "$CLUSTER_DIR/source" && git pull --ff-only)

    info "同步代码到 scanner（排除 config.json / data / docker-compose.yml）"
    rsync -a --delete \
        --exclude config.json \
        --exclude data/ \
        --exclude docker-compose.yml \
        "$CLUSTER_DIR/source/" \
        "$CLUSTER_DIR/scanner/fakabot/"

    info "同步代码到 6 个机器人"
    for bot in "${BOTS[@]}"; do
        rsync -a --delete \
            --exclude config.json \
            --exclude data/ \
            --exclude docker-compose.yml \
            "$CLUSTER_DIR/source/" \
            "$CLUSTER_DIR/$bot/fakabot/"
    done

    info "重建并重启共享扫链服务"
    (cd "$CLUSTER_DIR/scanner/fakabot" && docker compose --profile multi-bot up -d --build usdt_scanner)
    info "重建并重启 6 个机器人"
    for bot in "${BOTS[@]}"; do
        (cd "$CLUSTER_DIR/$bot/fakabot" && docker compose up -d --build sp_shop_bot)
    done
    echo "✅ 更新完成"
    cmd_verify
}

# ---------------------------------------------------------------------------
# 备份（0.16）
# ---------------------------------------------------------------------------
cmd_backup() {
    mkdir -p "$BACKUP_DIR"
    local archive="$BACKUP_DIR/fakabot-$(date +%F-%H%M%S).tar.gz"
    local targets=()
    for bot in "${BOTS[@]}"; do
        targets+=("$CLUSTER_DIR/$bot/data")
    done
    tar -czf "$archive" "${targets[@]}" "$CLUSTER_DIR/shared"
    echo "✅ 备份完成: $archive"
    ls -lh "$archive"
}

# ---------------------------------------------------------------------------
# 0.11 生成 Nginx location 片段（供手动/自动两种模式复用）
# ---------------------------------------------------------------------------
gen_nginx_locations() {
    local out="$1"
    : > "$out"
    local i=1
    for bot in "${BOTS[@]}"; do
        local port="${APP_PORTS[$((i - 1))]}"
        local dv="BOT0${i}_DOMAIN"
        local domain_val="${!dv}"
        local path="/${domain_val##*/}"
        cat >> "$out" <<EOF
location = ${path} {
    return 301 ${path}/;
}

location ${path}/ {
    proxy_pass http://127.0.0.1:${port}/;
    proxy_set_header Host \$host;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;
    proxy_set_header X-Forwarded-Prefix ${path};
}

EOF
        i=$((i + 1))
    done
}

# 手动模式：仅生成 location 片段文件
cmd_nginx() {
    load_env
    local out="$CLUSTER_DIR/nginx-fakabot-locations.conf"
    gen_nginx_locations "$out"
    echo "✅ 已生成 Nginx location 片段: $out"
    echo ""
    echo "提示：如需全自动完成 Nginx 安装、证书申请与转发配置，直接执行 $0 nginx-setup。"
    echo "手动并入步骤（按文档 0.11.1~0.11.3 先装好 Nginx 和证书）："
    echo "  1. 找到主域名配置: grep -R 'server_name pay.unishopasa.cn' -n /etc/nginx/sites-enabled /etc/nginx/sites-available /etc/nginx/conf.d"
    echo "  2. 备份原文件后，把 $out 的内容复制进对应的 HTTPS server { ... } 块内"
    echo "  3. nginx -t 校验通过后: systemctl reload nginx"
    echo "  4. 验证: curl -I https://pay.unishopasa.cn/bot11/health"
    echo ""
    echo "注意：本项目默认轮询模式（USE_WEBHOOK=false），无需转发 webhook。"
    echo "      若开启 USE_WEBHOOK=true，需为每个 /bot1X/tg/webhook 单独转发到备用端口 58301~58306（见部署文档 0.11 节）。"
}

# ---------------------------------------------------------------------------
# 0.11.1~0.11.4 全自动：安装 Nginx + 申请 HTTPS 证书 + 配置 6 组转发
# ---------------------------------------------------------------------------
main_domain() {
    local d="${BOT01_DOMAIN:-}"
    d="${d#*://}"
    d="${d%%/*}"
    printf '%s' "$d"
}

cmd_nginx_setup() {
    load_env
    [[ "$(id -u)" == "0" ]] || die "nginx-setup 需要 root 权限（apt/证书/nginx 配置）"

    local domain
    domain="$(main_domain)"
    [[ -n "$domain" ]] || die "无法从 BOT01_DOMAIN 提取主域名"

    info "检查/安装 Nginx 与 Certbot"
    if command -v nginx >/dev/null 2>&1 && command -v certbot >/dev/null 2>&1; then
        echo "✅ nginx 和 certbot 已安装"
    else
        apt-get update
        apt-get install -y nginx certbot python3-certbot-nginx
    fi

    info "放行 80/443 端口（ufw）"
    if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q "Status: active"; then
        ufw allow 80/tcp
        ufw allow 443/tcp
    fi

    info "检查 DNS 解析: $domain"
    local resolved_ip public_ip
    resolved_ip="$(getent hosts "$domain" 2>/dev/null | awk '{print $1}' | head -n1 || true)"
    [[ -n "$resolved_ip" ]] || die "域名 $domain 尚未解析，请先在域名服务商把 A 记录指向本服务器公网 IP"
    public_ip="$(curl -fsS --max-time 10 https://api.ipify.org 2>/dev/null || true)"
    if [[ -n "$public_ip" && "$resolved_ip" != "$public_ip" ]]; then
        die "域名 $domain 解析到 $resolved_ip，但本服务器公网 IP 是 $public_ip，请先修正 DNS 解析"
    fi
    echo "✅ $domain -> $resolved_ip"

    info "准备 HTTP 站点配置（80 端口）"
    local site_conf="/etc/nginx/sites-available/${domain}.conf"
    if [[ ! -f "$site_conf" ]]; then
        cat > "$site_conf" <<EOF
server {
    listen 80;
    server_name ${domain};

    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }
}
EOF
        ln -s "$site_conf" /etc/nginx/sites-enabled/ 2>/dev/null || true
        nginx -t && systemctl reload nginx
        echo "✅ 已创建 $site_conf"
    else
        echo "✅ $site_conf 已存在，跳过创建"
    fi

    info "申请 Let's Encrypt HTTPS 证书"
    local cert_path="/etc/letsencrypt/live/${domain}/fullchain.pem"
    if [[ -f "$cert_path" ]]; then
        echo "✅ 证书已存在: $cert_path"
    elif [[ -n "${CERTBOT_EMAIL:-}" && "$CERTBOT_EMAIL" != *"你的邮箱"* ]]; then
        certbot --nginx -d "$domain" -m "$CERTBOT_EMAIL" --agree-tos --redirect --non-interactive
    else
        echo "⚠️ 未在 deploy.env 配置 CERTBOT_EMAIL，将使用 --register-unsafely-without-email 申请"
        certbot --nginx -d "$domain" --register-unsafely-without-email --agree-tos --redirect --non-interactive
    fi

    info "生成 6 组 location 转发配置"
    gen_nginx_locations "/etc/nginx/fakabot-locations.conf"

    info "把 include 插入 HTTPS server 块"
    local conf_file
    conf_file="$(grep -Rl --exclude='*.bak*' "server_name ${domain}" /etc/nginx/sites-enabled /etc/nginx/sites-available 2>/dev/null | head -n1 || true)"
    [[ -n "$conf_file" ]] || die "找不到 ${domain} 的 nginx 配置文件"
    python3 - "$conf_file" <<'PY'
import sys

path = sys.argv[1]
with open(path, encoding="utf-8") as f:
    lines = f.readlines()
if any("fakabot-locations.conf" in ln for ln in lines):
    print(f"[OK] {path} 已包含 include，跳过插入")
    sys.exit(0)

out = []
in_443 = False
inserted = False
for ln in lines:
    out.append(ln)
    s = ln.strip()
    if not in_443 and "listen" in s and "443" in s and "ssl" in s:
        in_443 = True
    if in_443 and s.startswith("server_name") and not inserted:
        out.append("    include /etc/nginx/fakabot-locations.conf;  # fakabot multi-bot\n")
        inserted = True
    if in_443 and s == "}":
        in_443 = False

if not inserted:
    raise SystemExit(f"未能在 {path} 的 443 server 块中找到 server_name 行，请手动添加 include 行")

with open(path, "w", encoding="utf-8") as f:
    f.writelines(out)
print(f"[OK] 已在 {path} 插入 include")
PY

    info "校验并重载 Nginx"
    nginx -t
    systemctl reload nginx

    info "验证 6 个路径"
    local i=1 ok=1
    for bot in "${BOTS[@]}"; do
        local dv="BOT0${i}_DOMAIN"
        local domain_val="${!dv}"
        local path="/${domain_val##*/}"
        local code
        code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "https://${domain}${path}/health" || true)"
        if [[ "$code" == "200" ]]; then
            echo "✅ https://${domain}${path}/health -> 200"
        else
            echo "❌ https://${domain}${path}/health -> ${code:-无响应}"
            ok=0
        fi
        i=$((i + 1))
    done

    echo ""
    if [[ "$ok" == "1" ]]; then
        echo "✅ Nginx + HTTPS 配置完成，6 个机器人转发全部正常"
    else
        echo "⚠️ 部分路径未通过，请确认 6 个机器人容器已启动（$0 status）"
    fi
    echo "证书自动续期由 certbot systemd timer 负责，可用 systemctl list-timers | grep certbot 检查"
}

# ---------------------------------------------------------------------------
# 日常运维
# ---------------------------------------------------------------------------
cmd_status() {
    docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | grep -E 'NAMES|fakabot' || true
}

cmd_logs() {
    local target="${1:-}" flag="${2:-}"
    [[ -n "$target" ]] || { usage; return 1; }
    local container=""
    if [[ "$target" == "scanner" ]]; then
        container="fakabot-usdt-scanner"
    elif [[ " ${BOTS[*]} " == *" $target "* ]]; then
        container="fakabot-$target"
    else
        echo "❌ 未知目标: $target（可选 ${BOTS[*]} scanner）" >&2
        return 1
    fi
    if [[ "$flag" == "--follow" ]]; then
        docker logs -f --tail 200 "$container"
    else
        docker logs --tail 300 "$container"
    fi
}

cmd_restart() {
    local target="${1:-}"
    case "$target" in
        scanner)
            (cd "$CLUSTER_DIR/scanner/fakabot" && docker compose --profile multi-bot restart usdt_scanner)
            ;;
        bot01|bot02|bot03|bot04|bot05|bot06)
            (cd "$CLUSTER_DIR/$target/fakabot" && docker compose restart sp_shop_bot)
            ;;
        all)
            for bot in "${BOTS[@]}"; do
                (cd "$CLUSTER_DIR/$bot/fakabot" && docker compose restart sp_shop_bot)
            done
            (cd "$CLUSTER_DIR/scanner/fakabot" && docker compose --profile multi-bot restart usdt_scanner)
            ;;
        *) usage ;;
    esac
}

cmd_stop() {
    local target="${1:-}"
    case "$target" in
        scanner)
            (cd "$CLUSTER_DIR/scanner/fakabot" && docker compose --profile multi-bot stop usdt_scanner)
            ;;
        bot01|bot02|bot03|bot04|bot05|bot06)
            (cd "$CLUSTER_DIR/$target/fakabot" && docker compose stop sp_shop_bot redis)
            ;;
        all)
            for bot in "${BOTS[@]}"; do
                (cd "$CLUSTER_DIR/$bot/fakabot" && docker compose stop)
            done
            (cd "$CLUSTER_DIR/scanner/fakabot" && docker compose --profile multi-bot stop usdt_scanner)
            ;;
        *) usage ;;
    esac
}

# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------
cmd_deploy() {
    cmd_prepare
    cmd_gen_configs
    cmd_patch_compose
    cmd_build
    cmd_start
    echo ""
    echo "🎉 部署完成。请继续："
    echo "   1. 执行 $0 nginx-setup 自动完成 Nginx 安装、证书申请与转发配置"
    echo "   2. Telegram 中每个机器人 /start、/admin 初始化后台"
    echo "   3. 后台配置 USDT 收款地址、汇率、最小金额并开启 USDT(TRC20直付)"
}

main() {
    case "${1:-}" in
        init)       cmd_init ;;
        deploy)     cmd_deploy ;;
        prepare)    cmd_prepare ;;
        configs)    cmd_gen_configs ;;
        compose)    cmd_patch_compose ;;
        build)      cmd_build ;;
        start)      cmd_start ;;
        verify)     cmd_verify ;;
        update)     cmd_update ;;
        backup)     cmd_backup ;;
        nginx)      cmd_nginx ;;
        nginx-setup) cmd_nginx_setup ;;
        status)     cmd_status ;;
        logs)       shift; cmd_logs "$@" ;;
        restart)    shift; cmd_restart "$@" ;;
        stop)       shift; cmd_stop "$@" ;;
        -h|--help|help) usage ;;
        *)
            echo "❌ 未知子命令: ${1:-}" >&2
            usage
            ;;
    esac
}

main "$@"
