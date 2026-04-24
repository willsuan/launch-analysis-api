#!/usr/bin/env bash
# deploy_to_vm.sh
# Runs on your LAPTOP. Shows you the exact steps to bootstrap the project on
# your class VM. Because the class bastion requires TACC password + MFA,
# this script prints commands for you to execute interactively rather than
# trying to chain SSH through MFA non-interactively.
#
# Usage:
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

bold() { printf '\033[1m%s\033[0m' "$*"; }
blue() { printf '\033[1;34m%s\033[0m' "$*"; }
green() { printf '\033[1;32m%s\033[0m' "$*"; }

cat <<EOF
$(blue "Artemis Launch API — VM Deployment Helper")

The class VM isn't reachable from your laptop directly; you have to hop
through the TACC bastion first. Since login requires your password + MFA
token, we can't fully automate the chain. Follow these steps:

$(bold "Step 1.") SSH to the TACC bastion:

  $(green "ssh ${TACC_USER}@${BASTION}")

  Enter your TACC password, then your MFA token.

$(bold "Step 2.") From the bastion, SSH to your personal VM:

  $(green "ssh ${VM_ALIAS}")

  You should now be logged in as user 'ubuntu' on the class VM.

$(bold "Step 3.") Run the bootstrap script directly from GitHub:

  $(green "curl -fsSL https://raw.githubusercontent.com/willsuan/launch-analysis-api/main/scripts/vm_bootstrap.sh | bash")

  This installs Docker, kubectl, clones the repo, installs Python deps,
  and runs the test suite. It prints next-step commands when finished.

$(bold "Step 4.") (Optional) Expose the API from the VM so you can hit it
  from your laptop via a port-forward through the bastion. In a separate
  terminal on your laptop:

  $(green "ssh -L 5000:${VM_ALIAS}:5000 ${TACC_USER}@${BASTION}")

  Then in your browser visit http://localhost:5000/help

EOF

# Optionally scp the bootstrap script to the bastion, so you can run it
# without curl if the VM lacks egress for some reason.
if [[ -f "$(dirname "$0")/vm_bootstrap.sh" ]]; then
    cat <<EOF
$(bold "Alternative") — copy the bootstrap script through the bastion:

  $(green "scp $(dirname "$0")/vm_bootstrap.sh ${TACC_USER}@${BASTION}:~/")

  Then on the bastion:
  $(green "scp vm_bootstrap.sh ${VM_ALIAS}:~/")
  $(green "ssh ${VM_ALIAS} 'bash ~/vm_bootstrap.sh'")

EOF
fi
