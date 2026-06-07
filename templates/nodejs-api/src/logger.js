'use strict';

const pino = require('pino');

const logger = pino({
  level: process.env.LOG_LEVEL || 'info',
  ...(process.env.NODE_ENV === 'development' ? {
    transport: {
      target: 'pino-pretty',
      options: { colorize: true, translateTime: 'SYS:standard' },
    },
  } : {}),
  // Production: JSON structured logging — ingested by Loki/ELK/CloudWatch
  base: {
    service: process.env.SERVICE_NAME || 'nodejs-api',
    version: process.env.APP_VERSION || '1.0.0',
    env: process.env.NODE_ENV || 'production',
  },
  redact: {
    paths: ['req.headers.authorization', 'req.headers.cookie', '*.password', '*.token', '*.secret'],
    censor: '[REDACTED]',
  },
  serializers: {
    err: pino.stdSerializers.err,
    req: pino.stdSerializers.req,
    res: pino.stdSerializers.res,
  },
});

module.exports = logger;
