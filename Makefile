ifneq (,$(wildcard .env))
include .env
endif

PLUGIN_NAME   = Stocks
PACKAGE_NAME  = enigma2-plugin-extensions-stocks
VERSION := $(shell cat VERSION 2>/dev/null | tr -d '[:space:]')

BUILD_DIR        = build
IPK_WORK_DIR     = $(BUILD_DIR)/ipk
DATA_STAGING     = $(IPK_WORK_DIR)/data
CONTROL_STAGING  = $(IPK_WORK_DIR)/control

PLUGIN_PATH  = usr/lib/enigma2/python/Plugins/Extensions/$(PLUGIN_NAME)
OUTPUT_IPK   = $(BUILD_DIR)/$(PACKAGE_NAME)_$(VERSION)_all.ipk

DOS2UNIX_BIN := $(shell command -v dos2unix 2>/dev/null)
MSGFMT_BIN  := $(shell command -v msgfmt 2>/dev/null)

.PHONY: compile-locales all build clean normalize prepare ipk install copy-settings apply restart deploy

all: ipk

build: ipk

clean:
	rm -rf $(BUILD_DIR)

normalize:
ifneq ($(DOS2UNIX_BIN),)
	find src control -type f -exec dos2unix {} \;
endif

compile-locales:
ifneq ($(MSGFMT_BIN),)
	@for lang in de en it es; do \
		po=src/$(PLUGIN_NAME)/locale/$$lang/LC_MESSAGES/$(PLUGIN_NAME).po; \
		mo=src/$(PLUGIN_NAME)/locale/$$lang/LC_MESSAGES/$(PLUGIN_NAME).mo; \
		if [ -f "$$po" ]; then \
			$(MSGFMT_BIN) -o "$$mo" "$$po"; \
		fi; \
	done
else
	@echo "msgfmt not found - skipping locale compilation"
endif


prepare: normalize compile-locales
	mkdir -p $(DATA_STAGING)/$(PLUGIN_PATH)
	mkdir -p $(CONTROL_STAGING)
	cp -r src/$(PLUGIN_NAME)/* $(DATA_STAGING)/$(PLUGIN_PATH)/
	cp control/control  $(CONTROL_STAGING)/
	sed -i 's/^Version:.*/Version: $(VERSION)/' $(CONTROL_STAGING)/control
	cp control/postinst $(CONTROL_STAGING)/
	cp control/prerm    $(CONTROL_STAGING)/
	chmod 755 $(CONTROL_STAGING)/postinst $(CONTROL_STAGING)/prerm

ipk: clean prepare
	cd $(IPK_WORK_DIR) && \
	tar -czf data.tar.gz    -C data    . && \
	tar -czf control.tar.gz -C control . && \
	echo "2.0" > debian-binary && \
	ar r $(PACKAGE_NAME)_$(VERSION)_all.ipk debian-binary control.tar.gz data.tar.gz
	mv $(IPK_WORK_DIR)/$(PACKAGE_NAME)_$(VERSION)_all.ipk $(OUTPUT_IPK)

install: ipk
	@test -n "$(BOX_HOST)" && test -n "$(BOX_PORT)" && test -n "$(BOX_USER)"
	scp -P $(BOX_PORT) $(OUTPUT_IPK) $(BOX_USER)@$(BOX_HOST):/tmp/
	ssh -p $(BOX_PORT) $(BOX_USER)@$(BOX_HOST) \
	    "opkg install --force-reinstall /tmp/$(PACKAGE_NAME)_$(VERSION)_all.ipk"

copy-settings:
	@test -n "$(BOX_HOST)" || (echo "BOX_HOST not set"; exit 1)
	@if grep -qE '^STOCKS_WATCHLIST=' .env 2>/dev/null; then \
		WATCHLIST=$$(grep '^STOCKS_WATCHLIST=' .env | head -1 | cut -d= -f2-); \
		if [ -z "$$WATCHLIST" ]; then \
			echo "STOCKS_WATCHLIST is empty - skipping"; \
		else \
			echo "Resolving watchlist: $$WATCHLIST"; \
			RESOLVED=$$(python3 -c " \
import sys; sys.path.insert(0, 'src'); \
from Stocks.core.api import YahooFinanceClient; \
api = YahooFinanceClient(); \
raw = '$$WATCHLIST'.split(','); \
symbols = []; \
for item in raw: \
    item = item.strip(); \
    if not item: continue; \
    if '.' in item and len(item) <= 12: \
        symbols.append(item); continue; \
    results = api.search(item); \
    if results: \
        symbols.append(results[0]['symbol']); \
        print('  %s -> %s (%s)' % (item, results[0]['symbol'], results[0].get('name','')), file=sys.stderr); \
    else: \
        print('  %s -> NOT FOUND (skipped)' % item, file=sys.stderr); \
print(','.join(symbols)); \
			"); \
			if [ -n "$$RESOLVED" ]; then \
				echo "Deploying symbols: $$RESOLVED"; \
				scp -P $(BOX_PORT) .env $(BOX_USER)@$(BOX_HOST):/tmp/_stocks_env; \
				ssh -p $(BOX_PORT) $(BOX_USER)@$(BOX_HOST) 'set -e; \
					SF=/etc/enigma2/settings; TMP=/tmp/_settings_tmp; \
					touch $$SF; \
					grep -v "^config\.plugins\.stocks\." $$SF > $$TMP || true; \
					printf "%s\n" "config.plugins.stocks.watchlist='"$$RESOLVED"'" >> $$TMP; \
					mv $$TMP $$SF; rm -f /tmp/_stocks_env; \
					echo "Watchlist deployed to settings"'; \
			else \
				echo "No symbols resolved - skipping"; \
			fi; \
		fi; \
	else \
		echo "No STOCKS_WATCHLIST in .env - skipping"; \
	fi

apply:
	@test -n "$(BOX_HOST)" && test -n "$(BOX_PORT)" && test -n "$(BOX_USER)"
	ssh -p $(BOX_PORT) $(BOX_USER)@$(BOX_HOST) \
	    "init 4 >/dev/null 2>&1 || killall -9 enigma2 >/dev/null 2>&1 || true; sleep 2; init 3 >/dev/null 2>&1 || true"

restart: apply

deploy: install copy-settings apply
