# Vendored Zalo bridge sources

The runtime installs these pinned sources instead of downloading mutable global
packages during setup:

- `hermes-zalo-plugin`: upstream `cuongdev/hermes-zalo-plugin`, MIT.
- `zca-js`: upstream `RFS-ADRENO/zca-js`, MIT, with the deprecated `crypto-js`
  dependency replaced by Node.js `node:crypto` primitives.

Each project retains its upstream license and repository metadata. Refreshes
must preserve the native-crypto compatibility test and regenerate npm lockfiles.
