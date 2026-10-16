# Bellworks physics prediction, round 2 (BW-PREDICT-002)

[中文操作指南](README.zh-CN.md)

Four fixed initial variations: lower barrier, narrower offset barrier, removal of original domino 04, and one-tenth ball density. The original homepage and runtime source stay unchanged. A separate `round2.html` uses the same renderer and passive Rapier machine.

- **Bellworks-Round2-AI-Input.zip**: initial-only images, exact exported parameters, Chinese instructions and blank response. Give only this material to the prediction model.
- **Bellworks-Round2-Operator-Kit.zip**: measured answers, real solver/browser evidence and dependency-free Node scoring. Keep away from the prediction model until its original answer has been saved.

Every configuration has three fresh-world 30-second solver runs and three production-browser runs. Operator validation distinguishes deterministic replay from independent test cases. Model prediction performance is not implied by software tests.

See the Chinese guide for controls, offline use, freeze/score commands, regeneration and limitations. Never upload the entire repository or operator kit as model input.
