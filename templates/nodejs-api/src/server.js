'use strict';

// Initialise OpenTelemetry BEFORE any other imports
require('./tracing');

const app = require('./app');
const logger = require('./logger');

const PORT = parseInt(process.env.PORT || '8080', 10);
const HOST = process.env.HOST || '0.0.0.0';

const server = app.listen(PORT, HOST, () => {
  logger.info({ port: PORT, host: HOST, env: process.env.NODE_ENV }, 'Server started');
});

// Graceful shutdown — critical for zero-downtime rolling deploys
const shutdown = (signal) => {
  logger.info({ signal }, 'Graceful shutdown initiated');
  server.close((err) => {
    if (err) {
      logger.error({ err }, 'Error during shutdown');
      process.exit(1);
    }
    logger.info('Server closed cleanly');
    process.exit(0);
  });

  // Force exit after 30s
  setTimeout(() => {
    logger.error('Forced shutdown after timeout');
    process.exit(1);
  }, 30_000).unref();
};

process.on('SIGTERM', () => shutdown('SIGTERM'));
process.on('SIGINT', () => shutdown('SIGINT'));

process.on('uncaughtException', (err) => {
  logger.fatal({ err }, 'Uncaught exception — shutting down');
  process.exit(1);
});

process.on('unhandledRejection', (reason) => {
  logger.fatal({ reason }, 'Unhandled promise rejection — shutting down');
  process.exit(1);
});

module.exports = server;
