# Frame — AI Image Process

A local product-image workspace built around selective AI background removal, batch whitespace cropping, human review and correction, and ZIP export.

**Upload status:** Architecture documentation is available below. The application source was implemented locally and passed 10 backend tests plus the frontend production build, but the computer disconnected before the full source upload. This repository is not runnable yet.

[Architecture and design decisions](docs/DECISIONS.md) explains the programming languages, frameworks, model, storage, editor controls, processing behavior, export format, and tradeoffs.

The local implementation includes batch upload, per-image AI flags, auto-crop, manual crop, restore/erase brushes, undo, original/processed comparison, approvals, persistent batches, and PNG ZIP export.

Demo material was prepared using original generic device illustrations and a separately attributed iPhone 15 Pro Max photo. No employer code, internal systems, private product photos, credentials, uploads, or model weights are published here.

The full tested source and credited assets still need to be uploaded from the local checkout. Live browser review and real-model inference remain unverified.
