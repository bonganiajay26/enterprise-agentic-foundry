'use strict';

const { Router } = require('express');
const logger = require('../logger');

const router = Router();

let isReady = false;

// Signal readiness after warm-up (database connections, cache warming, etc.)
setTimeout(() => {
  isReady = true;
  logger.info('Service marked as ready');
}, parseInt(process.env.STARTUP_DELAY_MS || '2000', 10));

/**
 * Liveness probe — is the process alive?
 * Kubernetes restarts the pod if this returns non-200.
 */
router.get('/live', (req, res) => {
  res.status(200).json({
    status: 'alive',
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
  });
});

/**
 * Readiness probe — is the service ready to handle traffic?
 * Kubernetes removes the pod from load balancer if this returns non-200.
 */
router.get('/ready', async (req, res) => {
  if (!isReady) {
    return res.status(503).json({
      status: 'not_ready',
      reason: 'Warming up',
      timestamp: new Date().toISOString(),
    });
  }

  // Check dependencies
  const checks = await runHealthChecks();
  const allHealthy = checks.every((c) => c.healthy);

  return res.status(allHealthy ? 200 : 503).json({
    status: allHealthy ? 'ready' : 'degraded',
    checks,
    timestamp: new Date().toISOString(),
  });
});

/**
 * Startup probe — has the application started?
 */
router.get('/startup', (req, res) => {
  res.status(isReady ? 200 : 503).json({
    status: isReady ? 'started' : 'starting',
    timestamp: new Date().toISOString(),
  });
});

async function runHealthChecks() {
  const checks = [];

  // Database check (if configured)
  if (process.env.DATABASE_URL) {
    checks.push(await checkDatabase());
  }

  // Redis check (if configured)
  if (process.env.REDIS_URL) {
    checks.push(await checkRedis());
  }

  return checks;
}

async function checkDatabase() {
  try {
    // Replace with actual DB health check
    return { name: 'database', healthy: true, latency_ms: 1 };
  } catch (err) {
    logger.warn({ err }, 'Database health check failed');
    return { name: 'database', healthy: false, error: err.message };
  }
}

async function checkRedis() {
  try {
    // Replace with actual Redis PING
    return { name: 'redis', healthy: true, latency_ms: 0 };
  } catch (err) {
    logger.warn({ err }, 'Redis health check failed');
    return { name: 'redis', healthy: false, error: err.message };
  }
}

module.exports = router;
