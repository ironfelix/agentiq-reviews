import { useEffect, useRef, useCallback } from 'react';

/**
 * Custom hook for polling data at regular intervals
 * @param callback - Function to call on each poll
 * @param interval - Polling interval in milliseconds (default: 10000 = 10s)
 * @param enabled - Whether polling is enabled (default: true)
 */
export function usePolling(
  callback: () => void | Promise<void>,
  interval: number = 10000,
  enabled: boolean = true
) {
  const savedCallback = useRef(callback);
  const intervalRef = useRef<number>(undefined);

  // Remember the latest callback
  useEffect(() => {
    savedCallback.current = callback;
  }, [callback]);

  // Start/stop polling based on enabled flag
  useEffect(() => {
    if (!enabled) {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
      return;
    }

    // Call immediately on mount
    const executeCallback = async () => {
      try {
        await savedCallback.current();
      } catch (error) {
        console.error('Polling error:', error);
      }
    };

    executeCallback();

    // Set up interval
    intervalRef.current = window.setInterval(executeCallback, interval);

    // Cleanup on unmount or when dependencies change
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [interval, enabled]);

  // Provide manual trigger function
  const trigger = useCallback(async () => {
    try {
      await savedCallback.current();
    } catch (error) {
      console.error('Manual polling trigger error:', error);
    }
  }, []);

  return { trigger };
}
