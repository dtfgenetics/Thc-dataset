# Diagnostic content quality standard

This standard defines the minimum shape of a diagnostic profile intended for user-facing differential ranking in THC Grow Doc. It is deliberately stricter than a symptom-list article because the application must separate plausible look-alikes, state uncertainty, and tell the user what evidence would change the conclusion.

## Core content contract

Every reviewed diagnostic profile should contain:

- A concise summary that describes the disorder or organism without claiming that a photograph alone proves the diagnosis.
- Affected plant parts and growth stages specific enough to help discriminate among look-alikes.
- Indicators that include both common visible symptoms and higher-value discriminators such as canopy position, tissue age, lesion geometry, underside/root findings, progression pattern, or organism evidence.
- Exclusions that state what observations actively weaken the diagnosis rather than merely listing unrelated conditions.
- A progression sequence that distinguishes early, intermediate, advanced, and post-correction observations where evidence supports those stages.
- Look-alikes that reflect realistic confusion sets used by growers and diagnosticians.
- Confirmation steps that identify the minimum additional images, measurements, microscopy, tissue/root-zone analysis, or laboratory methods needed to raise confidence.
- Immediate actions that preserve evidence and prevent avoidable spread or injury before destructive treatment begins.
- A corrective plan that is conditional on confirmation and separates cause correction from symptom recovery.
- Prevention guidance tied to the demonstrated failure mode rather than generic cultivation advice.
- Warnings that preserve experiment limits, host-transfer limits, image limits, and any human-review requirements.
- Claim-level sources and provenance for scientific, diagnostic, and intervention statements.

## Discriminator quality

Profiles should not be optimized by simply adding more symptoms. Repeated generic phrases such as yellowing, spotting, curl, wilt, stunting, or necrosis have low diagnostic value when shared across many profiles. Prefer indicators that answer at least one of these questions:

1. Where on the plant did the problem begin?
2. Which tissue age was affected first?
3. Is the pattern interveinal, marginal, vascular, stippled, water-soaked, concentric, powdery, distorted, or mechanically bounded?
4. Is there direct underside, root, crown, stem, flower, or organism evidence?
5. How did the pattern change over time?
6. Which measured root-zone, environmental, or analytical variable supports the proposed mechanism?
7. What observation would strongly favor the nearest look-alike instead?

A reviewed profile should contain enough discriminating material that matching a small subset of generic symptoms cannot automatically outweigh a more focused profile whose defining signs are substantially covered.

## Confidence and confirmation

Photo/video evidence is supporting evidence, not universal ground truth. Conditions requiring microscopy, culture, PCR/qPCR, sequencing, tissue analysis, root-zone chemistry, or another non-visual method must retain an explicit photo-only confidence ceiling. The response policy must name required confirmation methods when they are known.

The application should return no diagnosis when none of a candidate's actual indicators match. Growth stage, evidence-slot presence, history, or other contextual bonuses may refine a symptom-supported hypothesis but must not create one by themselves.

## User-facing answer contract

The leading result should explain:

- what observations support it;
- what observations contradict it;
- what important evidence is still missing;
- the nearest alternatives;
- what the user should inspect or measure next;
- what can be done safely before confirmation;
- what action should wait until confirmation;
- what change in follow-up would cause the diagnosis to be reconsidered.

The goal is not to sound certain. The goal is to make the next diagnostic decision more accurate.

## Dataset maintenance

Generated or derived records must remain distinguishable from canonical source data. Image/reference provenance and licensing must remain intact. Composite figures should not be treated as single-class training samples until panels are bounded, labeled, scientifically reviewed, source-grouped, and assigned to leakage-safe splits. New profile content should be checked against the nearest existing look-alikes so additions increase discrimination rather than duplicating generic symptom language.
