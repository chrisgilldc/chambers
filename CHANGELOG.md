# Changelog

## 0.1.1-alpha1
 - Merge python library and Home Assistant add-on. Same repository should now be pip-installable and HA-Add-Onable
 - Add caching mechanism. Chamber objects now have the ability to add and restore their state to a dump file.
 - Add-on will attempt to load cache on start-up if available, and then save state at the top of each hour.

## 0.1.0-alpha7
 - Bump to Chambers 0.1.0-alpha7. Removes whitespace in Senate's AM/PM indicator.

## 0.1.0-alpha6
 - Bump to Chambers 0.1.0-alpha6. Catches XML parse errors during updates and continues.

## 0.1.0-alpha5
 - Bump to Chambers 0.1.0-alpha5. Fixes Senate auto-update.

## 0.1.0-alpha4
 - Bump to Chambers 0.1.0-alpha4

## 0.1.0-alpha3
 - Bump to Chambers 0.1.0-alpha3
 - Initial logging option. Should make it prettier, but it seems to work.

## 0.1.0-alpha2
 - Bump to Chambers 0.1.0-alpha2

## 0.1.0-alpha1

- Initial release, seems to work, at least for me!