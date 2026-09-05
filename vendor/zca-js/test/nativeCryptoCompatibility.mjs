import assert from "node:assert/strict";

import { ParamsEncryptor, decodeAES, encodeAES, getSignKey } from "../dist/utils.js";

const base64Key = "MDEyMzQ1Njc4OWFiY2RlZg==";
const payload = '{"hello":"Zalo","n":7}';
const expectedBase64 = "Umc7HilJMSnXOxQzfBNzDt23AqnuvHWxSL02MfabwwI=";

assert.equal(encodeAES(base64Key, payload), expectedBase64);
assert.equal(decodeAES(base64Key, expectedBase64), payload);
assert.equal(
    ParamsEncryptor.encodeAES(
        "3FC4F0D2AB50057BCE0D90D9187A22B1",
        "2,device-imei,1700000000000",
        "hex",
        false,
    ),
    "b0624ee79576bf37715820f677b399a33dd21b820021db64dd7ddb2e779e2d49",
);
assert.equal(getSignKey("test", { b: "b", a: "a" }), "beef248b123cb5f21808d3da1eb2ac41");

console.log("PASS native crypto matches CryptoJS 4.2.0 compatibility vectors");
