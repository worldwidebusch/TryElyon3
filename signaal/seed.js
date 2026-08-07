#!/usr/bin/env node
'use strict';
/** Vul de database met demodata. Gebruik --reset om eerst leeg te maken. */

const { seed } = require('./lib/seed');

const reset = process.argv.includes('--reset');
const t0 = Date.now();
const uit = seed({ resetFirst: reset });

console.log(reset ? 'Database leeggemaakt en opnieuw gevuld.' : 'Demodata toegevoegd.');
for (const [k, v] of Object.entries(uit)) console.log(`  ${k.padEnd(16)} ${v}`);
console.log(`\nKlaar in ${Date.now() - t0} ms. Start het dashboard met: node signaal/server.js`);
