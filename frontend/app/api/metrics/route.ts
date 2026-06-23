import { NextResponse } from 'next/server';
import * as client from 'prom-client';

// Use global to persist registry across hot-reloads in development
const globalRef = global as unknown as {
  prometheusRegistry?: client.Registry;
};

function getOrCreateRegistry() {
  if (!globalRef.prometheusRegistry) {
    const registry = new client.Registry();
    
    // Enable default metrics collection (CPU, Memory, etc.)
    client.collectDefaultMetrics({ register: registry });
    
    globalRef.prometheusRegistry = registry;
  }
  return globalRef.prometheusRegistry;
}

export async function GET() {
  try {
    const registry = getOrCreateRegistry();
    const metrics = await registry.metrics();
    return new NextResponse(metrics, {
      headers: {
        'Content-Type': registry.contentType,
        'Cache-Control': 'no-store',
      },
    });
  } catch (error) {
    console.error('Error generating metrics:', error);
    return new NextResponse('Internal Server Error', { status: 500 });
  }
}
