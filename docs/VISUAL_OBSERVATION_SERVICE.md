# Visual Observation Service

The THC Grow Doc visual layer is an **observation extractor**, not an autonomous diagnosis model.

## Purpose

Uploaded plant images can be sent, only after an explicit user action, to a server-side multimodal provider. The provider may suggest visible features and exact strings from the controlled symptom vocabulary. The user must approve suggested symptoms before they are added to the structured diagnostic context.

The controlled differential engine, evidence gates, condition-specific response policies, laboratory-confirmation rules, and open-set uncertainty remain authoritative.

## Current provider

The production proxy is implemented at:

- `public/api/visual-observations.php`

The default configured model is:

- `gemini-2.5-flash-lite`

The browser never receives the Gemini API key. The PHP proxy calls the provider server-side.

## Required production configuration

Configure one server-side secret using either of these methods:

1. Environment variable:
   - `GEMINI_API_KEY`
2. Server/WordPress PHP constant:
   - `THC_GROW_DOC_GEMINI_API_KEY`

Do **not** put the key in Vite variables, committed JavaScript, HTML, GitHub source files, or browser-visible configuration.

Optional server-side model override:

- `THC_GROW_DOC_VISION_MODEL`

If no API key is configured, the endpoint returns HTTP 503 and the app continues to support manual symptom selection and structured differential ranking.

## Frontend endpoint

The browser defaults to:

- `/thc-grow-doc/api/visual-observations.php`

A non-secret endpoint override can be set at build time with:

- `VITE_VISUAL_OBSERVATION_ENDPOINT`

## Safety boundaries

The provider prompt explicitly prohibits:

- disease/deficiency/toxicity diagnosis from appearance;
- pathogen, viroid, or virus confirmation;
- hidden-cause inference;
- treatment recommendations;
- cultivar guessing;
- pest-species claims without a visible organism;
- following instructions embedded inside uploaded images.

The service returns only:

- neutral visible-condition summary;
- exact controlled indicator suggestions;
- visible-feature notes with observation confidence;
- uncertain features;
- image-quality limitations;
- suggested next views;
- an unknown/out-of-scope flag.

Server output is revalidated before returning to the browser. Any suggested controlled indicator not present in the current application-provided vocabulary is discarded.

## User approval gate

Model-selected indicators never enter `GrowContext.symptoms` automatically.

The `VisualObservationReview` component displays suggestions separately. A user must select the observations they agree with and press **Add selected observations**. Only then can they affect differential ranking.

This is deliberate: model observation confidence is not diagnostic confidence.

## Video handling

The browser does not send the original video to the provider in the current implementation. It samples up to three JPEG frames from the video and sends those frames together with the available still images. This reduces transfer size and keeps the provider focused on visible spatial evidence.

## Privacy and training

- Media remains local until the user explicitly requests visual analysis.
- DTF does not add user uploads to the THC training dataset through this feature.
- Provider handling is governed by the API account/tier configured by the site operator.
- User uploads remain excluded from training by default under the project data-provenance rules.

If a provider/tier is changed, update the in-product disclosure and this document before release.

## Abuse controls

The PHP endpoint currently enforces:

- same-origin requests when an Origin header is supplied;
- explicit visual-request header;
- per-IP request throttling;
- accepted image MIME types only;
- per-file and total upload limits;
- maximum evidence-image count;
- controlled indicator count/length limits;
- provider timeout;
- no-store responses.

For higher-volume public deployment, add edge/WAF rate limiting and bot protection in addition to the application-level throttle.

## Release verification

CI must pass:

1. source/data validation;
2. TypeScript checks;
3. unit tests;
4. PHP syntax validation;
5. Vite production build;
6. verification that `dist/api/visual-observations.php` exists.

A live release is not complete until the production endpoint is smoke-tested with a non-sensitive test plant image and verified to return controlled observations without exposing the API key.
