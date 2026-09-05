Hardened rule
Authorization Gate
Read the current `# DECISION` before any external action.
If VPS testing or rollout is not authorized, do not access the VPS.
If VPS testing is authorized, copy only the intended core-fix changes, apply
them without merging first, restart affected services, and monitor the
Hermes, Zalo, OmniRouter, and model-router logs.
Run the strongest authorized smoke test using representative cases.
Observe the actual response or artifact, not just process/HTTP success.
Verify classification, execution, response content, and regressions.
Gate
PASS: continue to Git merge workflow.
FAIL: STOP immediately.
Do not create/merge MRs.
Fix the core issue and repeat from VPS update → smoke test.
Merge Workflow — only after PASS
Create MR → merge into develop.
Create MR → merge into main.
Search for other existing MRs related to the same core fix/change.
If existing MRs are pending:
merge compatible ones;
if conflicts occur, keep the newest intended implementation;
resolve/remove superseded changes rather than reintroducing older logic.
Verify main contains the final expected core fix.
Production/VPS Update
Update VPS from main only.
Do not deploy from develop, feature branches, local uncommitted state, or an arbitrary commit.
Verify VPS commit/version matches main.
Run a final smoke test after deployment.
Critical hardening rules
The strongest authorized smoke test PASS is a hard gate before any merge.
Never merge first and test afterward.
Never deploy unverified code from a feature/develop branch.
main is the only source of truth for VPS deployment.
Newest valid implementation wins when conflicting MRs represent the same fix.
Never merge an older/superseded MR just because it already exists.
Only roll changes onto a VPS when the current decision explicitly authorizes
that action. After every authorized VPS update, observe the real user-facing
response.
If the response is wrong even when the process exits successfully, treat the smoke test as FAIL.
If any step fails, STOP → diagnose → fix → retest. Do not continue the pipeline.
Before merging, check git status, branch, commit, and diff to prevent unrelated changes from entering the merge.
After merging to main, verify the final main commit before updating VPS.
