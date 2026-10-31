# Check the forecast deadline before scoring a scheduling decision

A day-ahead load decision needs the forecast published before its deadline. Substituting a later file can change the error attributed to that decision.

**Current state: protocol fixed; source and analysis gates remain open.** This independent study will audit five fixed ERCOT operating days, 25–29 October 2026, across eight weather zones and the published system total. It compares a prior-day noon cutoff with two explicitly late cutoffs. A command-line exercise will reject a file published after the supplied deadline.

The archive metadata and four non-cohort schema files were inspected before this design. No target-day load values or error summaries have been retrieved. This is an archive-metadata-conditioned retrospective audit, not a blinded forecast experiment. The captured publication timestamps do not independently prove that each archived file is immutable or was delivered on time to an analyst.

The original EIA/NOAA proposal for learned residual corrections, calibrated intervals, seasons and balancing-authority holdouts remains unexecuted. This separate narrower source plan does not establish better reserves, savings, deployments or scientific novelty. See [the protocol](PROTOCOL.md) and [data rights](DATA_RIGHTS.md).
