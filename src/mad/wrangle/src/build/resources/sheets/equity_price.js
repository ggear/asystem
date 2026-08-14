// Google Sheets custom function for the wrangle equity.prices feed.
//
// Setup, once per sheet:
//   1. Extensions > Apps Script, paste this file into Code.gs
//   2. Extensions > Apps Script > Project Settings > Script Properties, add CF_ACCESS_CLIENT_ID and CF_ACCESS_CLIENT_SECRET (case-sensitive) from src/may/cloudflare/.env_all_key.
//   3. Use as =WRANGLE_PRICE("GOLD", "ASX")

var WRANGLE_SUFFIX = {
    '': '',
    'ASX': '.AX',
    'LON': '.L',
    'TSE': '.TO',
    'FRA': '.F',
    'NYSE': '',
    'NASDAQ': '',
    'NYSEARCA': '',
    'BATS': ''
};

function WRANGLE_PRICE(symbol, exchange) {
    var props = PropertiesService.getScriptProperties();
    var id = props.getProperty('CF_ACCESS_CLIENT_ID');
    var secret = props.getProperty('CF_ACCESS_CLIENT_SECRET');
    if (!id || !secret) throw new Error('Script Properties CF_ACCESS_CLIENT_ID and CF_ACCESS_CLIENT_SECRET are not set');
    if (!symbol) throw new Error('symbol is required, e.g. =WRANGLE_PRICE("BHP", "ASX")');
    var key = String(exchange || '').trim().toUpperCase();
    var suffix = WRANGLE_SUFFIX[key];
    if (suffix === undefined) throw new Error('unknown exchange [' + key + ']');
    var target = String(symbol).trim() + suffix;
    var started = new Date().getTime();
    var response = UrlFetchApp.fetch(
        'https://prices.janeandgraham.com/' + encodeURIComponent(target), {
            headers: {
                'CF-Access-Client-Id': id,
                'CF-Access-Client-Secret': secret
            },
            muteHttpExceptions: true
        });
    var elapsed = new Date().getTime() - started;
    if (response.getResponseCode() != 200) {
        console.log('WRANGLE_PRICE [%s] failed [%s] in [%sms]', target, response.getResponseCode(), elapsed);
        throw new Error(response.getContentText());
    }
    var price = JSON.parse(response.getContentText()).price;
    console.log('WRANGLE_PRICE [%s] price [%s] in [%sms]', target, price, elapsed);
    return price;
}
