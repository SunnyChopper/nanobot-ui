/**
 * Import smoke test. Loads Baileys and the built WhatsApp client.
 * Does not call connect() and does not open a socket.
 */
import { DisconnectReason } from '@whiskeysockets/baileys';
import { WhatsAppClient } from '../dist/whatsapp.js';

if (DisconnectReason.loggedOut !== 401) {
  console.error(
    `DisconnectReason.loggedOut must be 401, got ${String(DisconnectReason.loggedOut)}`,
  );
  process.exit(1);
}

const client = new WhatsAppClient({
  authDir: '/tmp/nanobot-whatsapp-bridge-smoke-unused',
  onMessage() {},
  onQR() {},
  onStatus() {},
});

if (!(client instanceof WhatsAppClient)) {
  console.error('WhatsAppClient constructor did not return an instance');
  process.exit(1);
}

console.log('bridge smoke ok');
