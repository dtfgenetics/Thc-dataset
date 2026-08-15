# Hostinger + WordPress deployment guide for the reference tool

This guide keeps the WordPress site as the public-facing front end while the reference search API runs as a lightweight local service.

## Option A: Subdomain for the API

Best option for a Hostinger site that already runs WordPress.

1. Create a subdomain such as `api.dtfseeds.com` or `tool.dtfseeds.com`.
2. Upload the project or connect via SSH.
3. Start the reference API:

```bash
cd /home/username/public_html/thc-dataset
PORT=4171 HOST=0.0.0.0 bash backend/start-reference-api.sh
```

4. Make sure the API is reachable from the public domain.
5. In WordPress, use the shortcode or embed script and set the `index_url` to the API endpoint or the published `reference-image-index.json` file.

## Option B: Publish the static JSON catalog

If Node is not available on the main WordPress host, the simplest route is to publish the JSON file in the site’s accessible public directory and point the widget to that static file.

Example:

```html
<div data-thc-reference-tool data-index-url="/reference-image-index.json">
  <input type="search" name="q" />
  <div data-results></div>
</div>
```

## WordPress snippet

Use the plugin shortcode in a page or custom HTML block:

```php
[thc_reference_tool title="Reference image search" index_url="/reference-image-index.json"]
```

## Important operational notes

- Keep the API behind a stable subdomain, not directly in the main WordPress PHP directory when possible.
- Do not expose raw dataset files unless they are properly licensed and approved.
- Keep a separate review process for any public image file used in training or display.
- Use a lock-step benchmark set and review all labels before they are used for production model decisions.

## Recommended production pattern

- WordPress page = public front end and user interface
- reference API = dataset lookup/search layer
- model training = external GPU environment, not Hostinger itself
- approved data = stored in versioned repo or CDN/object storage
