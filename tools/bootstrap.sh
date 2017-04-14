#!/usr/bin/env bash
#
# bootstrap.sh - Prepare the toolchain
#
# Usage:
#
#     ./boostrap.sh
#
set -eu


main() {
    # install bazel
    if [[ "$(uname)" == "Darwin" ]]; then
        brew cask list | grep '^java$' &>/dev/null || brew cask install java
        brew list | grep '^bazel$' &>/dev/null || brew install bazel
    else
        # bazel APT repositories
        echo "deb [arch=amd64] http://storage.googleapis.com/bazel-apt stable jdk1.8" | sudo tee /etc/apt/sources.list.d/bazel.list
        curl https://bazel.build/bazel-release.pub.gpg | sudo apt-key add -

        sudo apt-get update
        dpkg -s 'bazel' &>/dev/null || sudo apt-get install -y bazel
    fi

    # install compiler toolchain
    if [[ "$(uname)" != "Dawrin" ]]; then
        sudo apt-get install -y clang
    fi

    # install latex
    if [[ "$(uname)" == "Darwin" ]]; then
        brew cask install texlive-full
    else
        sudo apt-get install -y texlive-full biber
    fi
}
main $@
