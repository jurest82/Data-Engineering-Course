#!/bin/bash

COLOR_RED=$(tput setaf 1)
COLOR_GREEN=$(tput setaf 2)
COLOR_YELLOW=$(tput setaf 3)
COLOR_BLUE=$(tput setaf 4)
COLOR_MAGENTA=$(tput setaf 5)
COLOR_DEFAULT=$(tput sgr0)

EXEC_PATH=$(dirname $(readlink -f "$0"))
HOME_PATH=$EXEC_PATH/..
PYTHON_DIST_PACKAGES_PATH=/usr/local/lib/python3.13/site-packages
STEP=1
STEP_COUNT=4

echo "${COLOR_MAGENTA}${STEP}/$STEP_COUNT:${COLOR_GREEN} Configuring Git & Git LFS.${COLOR_DEFAULT}"
GIT_SCRIPT_PATH=$HOME_PATH/../.docker/git.sh
chmod +x $GIT_SCRIPT_PATH
. $GIT_SCRIPT_PATH
let STEP++

echo "$COLOR_BLUE"

echo "${COLOR_MAGENTA}${STEP}/$STEP_COUNT:${COLOR_GREEN} Installing Python Lambda layer dependencies.${COLOR_DEFAULT}"
for REQUIREMENTS_FILE in $HOME_PATH/src/layers/*/requirements.txt; do
    if [ -f "$REQUIREMENTS_FILE" ]; then
        LAYER_DIR=$(dirname "$REQUIREMENTS_FILE")
        LAYER_NAME=$(basename "$LAYER_DIR")
        echo "${COLOR_GREEN}INFO: Installing ${COLOR_BLUE}${REQUIREMENTS_FILE}${COLOR_DEFAULT}"
        (cd "$LAYER_DIR" && sudo pip install --root-user-action=ignore -r requirements.txt -t python)
        echo "$LAYER_DIR/python" | sudo tee "$PYTHON_DIST_PACKAGES_PATH/data-eng-course-backend-layers-$LAYER_NAME.pth" > /dev/null
    fi
done
let STEP++

if [ ! -d "$HOME_PATH/node_modules" ]; then
    echo "${COLOR_MAGENTA}${STEP}/$STEP_COUNT:${COLOR_GREEN} Installing ${COLOR_BLUE}$HOME_PATH/package.json${COLOR_GREEN} dependencies.${COLOR_DEFAULT}"
    cd $HOME_PATH && npm install
else
    echo "${COLOR_MAGENTA}${STEP}/$STEP_COUNT:${COLOR_GREEN} Folder ${COLOR_BLUE}$HOME_PATH/node_modules${COLOR_GREEN} found! Skipping npm installation.${COLOR_DEFAULT}"
fi
let STEP++

echo "${COLOR_MAGENTA}${STEP}/$STEP_COUNT:${COLOR_GREEN} Configuring AWS credentials.${COLOR_DEFAULT}"
AWS_SCRIPT_PATH=$HOME_PATH/../.docker/aws.sh
chmod +x $AWS_SCRIPT_PATH
echo "INFO: Execute permissions given to $HOME_PATH/../.docker/aws.sh file." 
$AWS_SCRIPT_PATH

ACCOUNT_ALIASES=$(aws iam list-account-aliases)
ACCOUNT_ALIAS=$(echo $ACCOUNT_ALIASES | jq -r '.AccountAliases[0]')
echo -e "${COLOR_GREEN}INFO: AWS account alias: ${ACCOUNT_ALIAS}${COLOR_DEFAULT}"

DEVELOPER_INFO=$(env | grep DEVELOPER)
echo -e "${COLOR_GREEN}INFO: Developer: ${DEVELOPER_INFO}${COLOR_DEFAULT}"

echo "$COLOR_DEFAULT"