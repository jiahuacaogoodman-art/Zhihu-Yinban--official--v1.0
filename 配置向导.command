#!/usr/bin/env bash
# 智护银伴 · macOS 图形化配置/部署入口

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/scripts/mac-gui-deploy.sh"
