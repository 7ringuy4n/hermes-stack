Hardened rule
Copy Core Fix → VPS
Copy only the intended core-fix changes.
Do not merge branches yet.
Update Core Fix on VPS
Apply/update the core fix.
Restart the affected service(s) if required.
Run Smoke Test
Test the new core fix using representative cases.
Observe the actual response, not just process/HTTP success.
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
Smoke test PASS is a hard gate before any merge.
Never merge first and test afterward.
Never deploy unverified code from a feature/develop branch.
main is the only source of truth for VPS deployment.
Newest valid implementation wins when conflicting MRs represent the same fix.
Never merge an older/superseded MR just because it already exists.
After every VPS update, observe the real user-facing response.
If the response is wrong even when the process exits successfully, treat the smoke test as FAIL.
If any step fails, STOP → diagnose → fix → retest. Do not continue the pipeline.
Before merging, check git status, branch, commit, and diff to prevent unrelated changes from entering the merge.
After merging to main, verify the final main commit before updating VPS.