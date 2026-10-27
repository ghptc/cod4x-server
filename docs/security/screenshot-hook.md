# Screenshot hook filename boundary

The optional Unix screenshot hook invokes a trusted configured program through a
shell. Double quotes around its filename argument do not prevent command
substitution. Before this fix, a player name containing `$()` or backticks could
survive screenshot basename validation and execute shell syntax when an operator
requested a screenshot and `sv_screenshotArrivedCmd` was configured. The default
hook is empty. No production hook or exploit was invoked during verification.

Portable ASCII letters, digits, underscore and hyphen now survive basename
validation; other bytes become underscores. Normal player names and screenshot
numbering remain intact. The optional hook's configured program/path remains
trusted operator input; this change does not turn general process launch into a
sandbox. Replacing shell-based hooks with argument-vector process launch remains
a broader follow-up.

`tests/test_screenshot_security.py` executes the real sanitizer and evaluates only
a harmless printf through the same double-quoted Unix argument boundary. It covers
command substitution, backticks, Windows expansion tokens, quote delimiters,
separators and path/control characters. No game client or remote endpoint is used.
Rollback is a reviewed revert; do not restore the vulnerable sanitizer while the
optional hook is in use. Deployment and any hook configuration require separate
operator approval.
