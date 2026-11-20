# Native QNS resolution: findings and next verification steps

## Current feasibility

The official [QNS Rust SDK](https://github.com/QuilibriumNetwork/quilibrium-names-sdk) is not a peer-to-peer resolver in its current implementation. `QnsClient::default()` uses `https://names.quilibrium.com`; `resolve()` performs `GET /resolve/{name}` and deserializes JSON. Its batch API also posts to that service. Integrating the SDK unchanged would preserve the centralized name-resolution dependency.

The SDK record type contains `header.authorityKey`, `name`, `parent`, timestamps, a derived `address`, and metadata. Its schema code can derive a record address from a complete record, but that API requires the record fields up front; it does not provide a documented deterministic name-to-record lookup key or a locally verifiable inclusion proof. The SDK README's use of “owner” and “Poseidon address” is not enough to establish that every `authorityKey` is an EVM wallet address. The current live `obscura` response has a 20-byte EVM-shaped `authorityKey`, but this one record does not prove the format used by every QNS identity.

## What a decentralized bridge would need

1. A protocol-native way to locate a record from a `.q` name without querying `names.quilibrium.com` or another name index.
2. A client/node API that returns the corresponding authenticated Hypergraph state or a proof verifiable against a trusted network commitment.
3. Exact rules for record schema, name hashing/normalization, parent names, authority-key encoding, and update/transfer ordering.
4. An identity verifier that supports the actual QNS authority key type. Do not assume EIP-191 if the QNS key is a Poseidon-derived Q identity or another key format.
5. A way to map the QNS record's destination metadata to the bridge's supported HTTP origins.

The existing SDK does not expose these pieces as a ready-to-use browser resolver. A direct QClient/Hypergraph implementation may be possible, but first needs the network's deterministic name index and verifiable read path. If the only way to find the record remains an HTTP resolver, replacing the host name does not make resolution decentralized.

## Recommended next step

Request or locate the canonical on-network QNS record schema and the official client-side proof/lookup API, including a known test vector for `obscura.q` (name → record address → authenticated record). Then prototype a read-only verifier against a public node/RPC, compare its result byte-for-byte with the current QNS API, and keep the static association list as fallback until arbitrary-name resolution works. No background node, external resolver, or blockchain transaction is needed for the current one-site bundled path.
