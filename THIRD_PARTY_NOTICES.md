# Third-Party Notices

## RescueMind AI (upstream project)

- Project: **RescueMind AI** — multi-agent disaster response platform
  (repository name `rescuemind-multi-agent`)
- Repository: https://github.com/BALADURGAG24/rescuemind-multi-agent
- License: MIT License
- Copyright: Copyright (c) 2026 BALADURGA G

MountainGuardian's initial codebase (first commit, 2026-09-27) incorporated
copies of RescueMind AI sources (several files byte-identical, e.g. the
original LICENSE, `agents/base_agent.py`, `mcp/mcp_servers.py`), i.e. a
modified derivative of the upstream MIT-licensed work. The MountainGuardian
v1.0 product code (deterministic risk engine, professional evidence agents,
synthesis/critic layer, Streamlit frontend, orchestration, providers,
deployment) was subsequently rewritten or added during the v1.0 engineering
gates; a small number of legacy upstream modules remain in the tree.
In accordance with the MIT License, the upstream copyright notice and
permission notice are retained in `LICENSE` and reproduced here.

## Python dependencies

Packages installed via `requirements.txt` (Streamlit, requests, pytest, and
others) are used under their respective upstream licenses; none impose
obligations beyond their own notices, which accompany each distribution.
