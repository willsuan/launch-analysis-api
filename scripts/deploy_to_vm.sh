#!/usr/bin/env bash
# Print the SSH chain to bootstrap the project on the class VM.
# The bastion needs password + MFA so we can't automate end-to-end.
#
#   ./scripts/deploy_to_vm.sh
#   ./scripts/deploy_to_vm.sh --tacc-user YOUR_TACC_USERNAME

set -euo pipefail

TACC_USER="${USER}"
BASTION="coe332-2026.tacc.cloud"
VM_ALIAS="coe332-vm"
REPO_URL="https://github.com/willsuan/launch-analysis-api.git"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --tacc-user) TACC_USER="$2"; shift 2 ;;
        -h|--help)
            grep '^# ' "$0" | sed 's/^# \?//'
            exit 0 ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

bold()  { printf '\033[1m%s\033[0m' "$*"; }
blue()  { printf '\033[1;34m%s\033[0m' "$*"; }
green() { printf '\033[1;32m%s\033[0m' "$*"; }

cat <<EOF
$(blue "VM deployment helper")

The class VM isn't directly reachable from your laptop; you hop through
the TACC bastion. Login requires password + MFA, so this script just
prints what to type.

$(bold "1.") SSH to the bastion:

  $(green "ssh ${TACC_USER}@${BASTION}")

  Password, then MFA token.

$(bold "2.") From the bastion, SSH to your VM:

  $(green "ssh ${VM_ALIAS}")

  You'll be 'ubuntu' on the VM.

$(bold "3.") Bootstrap from GitHub:

  $(green "curl -fsSL https://raw.githubusercontent.com/willsuan/launch-analysis-api/main/scripts/vm_bootstrap.sh | bash")

  Installs docker, kubectl, clones the repo, sets up the venv, runs pytest.

$(bold "4.") (optional) Forward port 5000 to your laptop so you can hit
  the local API from your browser. In a separate laptop terminal:

  $(green "ssh -L 5000:${VM_ALIAS}:5000 ${TACC_USER}@${BASTION}")

  Then visit http://localhost:5000/help.

EOF

# If the egress is broken on the VM you can scp the script through the bastion
# instead of curl-piping it.
if [[ -f "$(dirname "$0")/vm_bootstrap.sh" ]]; then
    cat <<EOF
fallback (no egress from VM): scp the bootstrap through the bastion.

  $(green "scp $(dirname "$0")/vm_bootstrap.sh ${TACC_USER}@${BASTION}:~/")

  On the bastion:
  $(green "scp vm_bootstrap.sh ${VM_ALIAS}:~/")
  $(green "ssh ${VM_ALIAS} 'bash ~/vm_bootstrap.sh'")

EOF
fi
