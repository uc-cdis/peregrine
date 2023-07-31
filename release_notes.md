# Release Notes

For: uc-cdis/peregrine

Notes since tag: 3.2.0

Notes to tag/commit: 3.2.1

Generated: 2023-07-31



## Improvement
  - Since there are some file having file_size larger than the largest possible 
    Int32 type in GraphQL, we need to extend it to use Float. ([#201](https://github.com/uc-cdis/peregrine/pull/201)) 

## Bug Fixes
  - Fix `/datasets` to correctly return an error when no `nodes` parameter is 
    provided ([#202](https://github.com/uc-cdis/peregrine/pull/202))

## Improvements
  - Log more error details in the core metadata endpoint ([#200](https://github.com/uc-cdis/peregrine/pull/200)) 

