#!/usr/bin/env node
// GitHub Pages 用のデータファイル（site/data.enc.js）を作る。
//
// 7つのデータ（JSON）をまとめて、パスワードから作った鍵で AES-GCM 暗号化する。
// ページはパスワードが合ったときだけ復号して表示する。平文のデータは公開しない。
//
// 使い方:
//   AICO_PASSWORD=xxxx node tools/build_site_data.mjs <データのフォルダ> [出力先=site/data.enc.js]
//
// パスワードはリポジトリに書かない（環境変数で渡す）。
// 注意: 短いパスワード（4桁の数字など）は総当たりで破られうる。気軽に見られないようにする
// ための仕組みで、強い秘密保持が必要なら非公開の場所に置くこと。
import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { webcrypto as crypto } from 'node:crypto';

const NAMES = ['weekly_total', 'weekly_category', 'monthly_total', 'monthly_category', 'monthly_trend', 'support_weekly', 'support_period'];
const ITER = 600000;

const [dir, out = 'site/data.enc.js'] = process.argv.slice(2);
const pw = (process.env.AICO_PASSWORD || '').trim();
if (!dir || !pw) {
  console.error('使い方: AICO_PASSWORD=xxxx node tools/build_site_data.mjs <データのフォルダ> [出力先]');
  process.exit(1);
}

const data = {};
for (const n of NAMES) {
  const rows = JSON.parse(readFileSync(join(dir, `${n}.json`), 'utf8'));
  if (!Array.isArray(rows) || !rows.length) throw new Error(`${n}.json が空か、配列ではありません`);
  data[n] = rows;
}

const b64 = (u8) => Buffer.from(u8).toString('base64');
const salt = crypto.getRandomValues(new Uint8Array(16));
const iv = crypto.getRandomValues(new Uint8Array(12));
const base = await crypto.subtle.importKey('raw', new TextEncoder().encode(pw), 'PBKDF2', false, ['deriveKey']);
const key = await crypto.subtle.deriveKey({ name: 'PBKDF2', salt, iterations: ITER, hash: 'SHA-256' }, base, { name: 'AES-GCM', length: 256 }, false, ['encrypt']);
const ct = new Uint8Array(await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, key, new TextEncoder().encode(JSON.stringify(data))));

const meta = { v: 1, kdf: 'PBKDF2-SHA256', iter: ITER, salt: b64(salt), iv: b64(iv), ct: b64(ct), built: new Date().toISOString() };
writeFileSync(out, `/* 暗号化したデータ（tools/build_site_data.mjs で作成）。パスワードがないと読めません。 */\nwindow.AICO_ENC = ${JSON.stringify(meta)};\n`);
console.log(`${out} を作成しました（${NAMES.map((n) => `${n} ${data[n].length}行`).join('、')}）`);
