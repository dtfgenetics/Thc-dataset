<?php
/**
 * Plugin Name: THC Reference Tool
 * Description: Adds a searchable reference-image tool block that reads the approved image catalog.
 * Version: 1.0.0
 */

function thc_reference_tool_shortcode($atts = []) {
    $atts = shortcode_atts([
        'title' => 'Reference image search',
        'index_url' => '/reference-image-index.json',
    ], $atts, 'thc_reference_tool');

    wp_enqueue_script(
        'thc-reference-tool-widget',
        plugin_dir_url(__FILE__) . 'reference-search-widget.js',
        [],
        '1.0.0',
        true
    );

    ob_start();
    ?>
    <div class="thc-reference-tool" data-thc-reference-tool data-index-url="<?php echo esc_url($atts['index_url']); ?>">
      <h3><?php echo esc_html($atts['title']); ?></h3>
      <label class="thc-reference-search">
        <span class="screen-reader-text">Search reference images</span>
        <input type="search" name="q" placeholder="Search dataset, label, file, or source tag" />
      </label>
      <div class="thc-reference-results" data-results></div>
    </div>
    <?php
    return ob_get_clean();
}

add_shortcode('thc_reference_tool', 'thc_reference_tool_shortcode');
