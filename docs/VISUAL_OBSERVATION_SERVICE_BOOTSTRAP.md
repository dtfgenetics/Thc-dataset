# Grow Doc visual API server bootstrap

The visual-observation endpoint is served directly at `public/api/visual-observations.php`, outside normal WordPress routing.

When `GEMINI_API_KEY` is available as a PHP environment variable, the endpoint uses it directly and does not bootstrap WordPress.

When the key is configured as the documented `THC_GROW_DOC_GEMINI_API_KEY` constant in `wp-config.php`, the endpoint conditionally loads the WordPress bootstrap before reading the constant. This keeps the key server-side while making the documented WordPress configuration path functional for the standalone endpoint.

The endpoint still returns HTTP 503 when neither server-side configuration path supplies a key. No key is emitted to HTML, JavaScript, API responses, logs, or committed source.
