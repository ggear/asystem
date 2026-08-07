################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

# domain/resolver [public DNS resolution of the monitored domain across the public resolvers]
#   cadence 15m
#   field ok - 15m [every resolver resolved and agreed on the same address set]
#   field score - 15m [diagnosis score from 0 to 100]
#   field resolvers_total - 15m [resolvers queried]
#   field resolvers_ok - 15m [resolvers agreeing with the consensus address set]
#   field resolvers_failed - 15m [resolvers that failed to resolve]

domain
    ok=<0|1>i,
    score=<number>i,
    resolvers_total=<number>i,
    resolvers_ok=<number>i,
    resolvers_failed=<number>i
    <timestamp>
