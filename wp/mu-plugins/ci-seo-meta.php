<?php
/**
 * Plugin Name: CI SEO Meta via REST
 * Description: Maakt de SEO-metavelden van Yoast SEO en Rank Math lees- en schrijfbaar via de WP REST API
 *              (voor CI Search Manager, src/wp_client.py). Alleen voor ingelogde gebruikers met edit-rechten.
 * Version: 1.0
 *
 * Installatie (Hostinger): hPanel → Bestandsbeheer → public_html/wp-content/mu-plugins/ (map aanmaken als die
 * ontbreekt) → dit bestand uploaden. Mu-plugins zijn direct actief, zonder activeren.
 */

if (!defined('ABSPATH')) {
    exit;
}

add_action('init', function () {
    $keys = [
        // Yoast SEO
        '_yoast_wpseo_title',
        '_yoast_wpseo_metadesc',
        '_yoast_wpseo_focuskw',
        // Rank Math
        'rank_math_title',
        'rank_math_description',
        'rank_math_focus_keyword',
    ];
    foreach (['post', 'page'] as $type) {
        foreach ($keys as $key) {
            register_post_meta($type, $key, [
                'show_in_rest'  => true,
                'single'        => true,
                'type'          => 'string',
                'sanitize_callback' => 'sanitize_text_field',
                'auth_callback'  => function () {
                    return current_user_can('edit_posts');
                },
            ]);
        }
    }
});
