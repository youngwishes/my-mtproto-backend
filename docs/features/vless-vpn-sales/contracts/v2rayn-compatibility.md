# External VLESS subscription compatibility gate

The independent acceptance fixture is pinned to the maintained primary client
`2dust/v2rayN` release `7.24.0`, commit
`5dd5b258690f93414692b30580f58b9650200ddd`. v2rayN documents VLESS subscription
and Base64/plaintext clipboard import in its project wiki.

The upstream parser source is
`v2rayN/ServiceLib/Handler/Fmt/VLESSFmt.cs`, SHA-256
`db41efd8d68c975697053a0583e4841d91e8f191c6f15d3bebd5b4de5986f636`.
The upstream license is GPL-3.0-only, LICENSE SHA-256
`c93d1d90b1111eae8bbc9824405d60186e0cc5f3e643d9feb3fa66e7629e7f17`.
No GPL source or runtime dependency is copied into this repository: the
test-only fixture records one exact URI accepted by that pinned parser and its
resolved fields. Its SHA-256 is
`ec9536981775851b264336473eabfb8ec57cc0f6e2b8f5934ec1d99be51e17e9`.
The generator must produce that URI byte-for-byte. The local
strict parser remains an additional structural gate, not the external proof.

Primary sources:

- https://github.com/2dust/v2rayN/tree/5dd5b258690f93414692b30580f58b9650200ddd
- https://github.com/2dust/v2rayN/wiki/Description-of-subscription
- https://github.com/2dust/v2rayN/wiki/Description-of-some-ui
