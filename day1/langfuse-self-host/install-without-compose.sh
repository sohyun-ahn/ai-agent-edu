#!/bin/bash
set -euo pipefail

# ============================================================
#  WSL Ubuntu — Docker Engine 설치 스크립트
#  실행: chmod +x install-docker-wsl.sh && ./install-docker-wsl.sh
# ============================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# ---------- 사전 체크 ----------
if [ "$(id -u)" -eq 0 ]; then
    error "root가 아닌 일반 사용자로 실행하세요 (sudo 붙이지 마세요)"
fi

if ! grep -qi microsoft /proc/version 2>/dev/null; then
    warn "WSL 환경이 아닌 것 같습니다. 계속 진행합니다..."
fi

# ---------- 1. 기존 패키지 제거 ----------
info "1/6 — 기존 Docker 관련 패키지 제거"
REMOVE_PKGS=(docker.io docker-doc docker-compose docker-compose-v2 podman-docker containerd runc)
for pkg in "${REMOVE_PKGS[@]}"; do
    sudo apt-get remove -y "$pkg" 2>/dev/null || true
done

# ---------- 2. 필수 패키지 설치 ----------
info "2/6 — 필수 패키지 설치"
sudo apt-get update -y
sudo apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

# ---------- 3. Docker 공식 GPG 키 & 저장소 추가 ----------
info "3/6 — Docker 공식 저장소 등록"
sudo install -m 0755 -d /etc/apt/keyrings

curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg --yes

sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# ---------- 4. Docker Engine 설치 ----------
info "4/6 — Docker Engine + CLI + Compose 설치"
sudo apt-get update -y
sudo apt-get install -y \
    docker-ce \
    docker-ce-cli \
    containerd.io \
    docker-buildx-plugin \
    docker-compose-plugin

# ---------- 5. 사용자 docker 그룹 추가 ----------
info "5/6 — 현재 사용자(${USER})를 docker 그룹에 추가"
sudo usermod -aG docker "$USER"

# ---------- 6. Docker 데몬 시작 ----------
info "6/6 — Docker 데몬 시작"

# systemd가 있는 경우 (WSL2 최신 버전)
if pidof systemd > /dev/null 2>&1; then
    sudo systemctl enable docker
    sudo systemctl start docker
    info "systemd로 Docker 시작 완료"
else
    # systemd 없는 구버전 WSL2
    sudo service docker start || true
    warn "systemd가 없어서 service 명령으로 시작했습니다"
    warn "WSL을 열 때마다 'sudo service docker start' 필요 (아래 가이드 참고)"
fi

# ---------- 설치 확인 ----------
echo ""
echo "==========================================="
info "설치 완료! 버전 정보:"
echo "==========================================="
docker --version
docker compose version
echo ""

warn "docker 그룹 반영을 위해 아래 중 하나를 실행하세요:"
echo "  1) newgrp docker        ← 현재 터미널에서 바로 적용"
echo "  2) WSL 재시작            ← PowerShell: wsl --shutdown"
echo ""
info "테스트: docker run hello-world"