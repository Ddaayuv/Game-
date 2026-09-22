<?php
// Railway Environment Variable: BOT_TOKEN
$token = getenv('BOT_TOKEN');

if (!$token) {
    http_response_code(500);
    exit('BOT_TOKEN is not configured.');
}

define('BOT_TOKEN', $token);
define('TG_API', 'https://api.telegram.org/bot' . BOT_TOKEN . '/');
