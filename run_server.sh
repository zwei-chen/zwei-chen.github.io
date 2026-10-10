#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

# Use the Homebrew Ruby installed for this Jekyll project.
for ruby_bin in /opt/homebrew/opt/ruby@3.3/bin /usr/local/opt/ruby@3.3/bin; do
  if [ -x "$ruby_bin/ruby" ]; then
    export PATH="$ruby_bin:$PATH"
    break
  fi
done

bundle config set --local path vendor/bundle
if ! bundle check >/dev/null 2>&1; then
  bundle install
fi
exec bundle exec jekyll serve --host 127.0.0.1 --port 4000
