# WhatsApp bridge dependency security

## Exact pins

Every entry in `dependencies` and `devDependencies` in `package.json` is an exact version. None use `^` or `~`. Those versions are the ones already resolved in `package-lock.json`, so pinning does not move the installed tree.

`bridge/.npmrc` sets `save-exact=true`. A later `npm install <pkg>` records an exact version instead of a range. Install from the lockfile with `npm ci`. Review any lockfile change before merging it; ranges on transitive dependencies are still only frozen by the lockfile.

## Baileys

`@whiskeysockets/baileys` is pinned to `7.0.0-rc13`.

[GHSA-qvv5-jq5g-4cgg](https://github.com/WhiskeySockets/Baileys/security/advisories/GHSA-qvv5-jq5g-4cgg) is a message-spoofing issue. It is fixed in `7.0.0-rc12` (and in `6.7.22` on the 6.x line). This bridge stays on `7.0.0-rc13` because that release keeps the rc12 fix and includes the `fromMe` correction. Do not pin an older 7.0.0 release candidate.

## whatsapp-rust-bridge

Baileys depends on `whatsapp-rust-bridge` (resolved at `0.5.4` in this lockfile). That package has a single maintainer, [jlucaso](https://www.npmjs.com/package/whatsapp-rust-bridge). Review the package, its native artifacts, and the diff on every bump before accepting a lockfile update.
