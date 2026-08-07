import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import * as SecureStore from 'expo-secure-store';

import { api } from '../api/client';

const SessionContext = createContext(null);

async function saveTokens(result) {
  await SecureStore.setItemAsync('access_token', result.access_token);
  await SecureStore.setItemAsync('refresh_token', result.refresh_token);
}

export function SessionProvider({ children }) {
  const [token, setToken] = useState(null);
  const [profileReady, setProfileReady] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const stored = await SecureStore.getItemAsync('access_token');
      setToken(stored);
      if (stored) {
        try {
          const profile = await api.getProfile();
          setProfileReady(Boolean(profile.username));
        } catch {
          await SecureStore.deleteItemAsync('access_token');
          await SecureStore.deleteItemAsync('refresh_token');
          setToken(null);
        }
      }
      setLoading(false);
    })();
  }, []);

  const value = useMemo(() => ({
    token,
    profileReady,
    loading,
    async login(email, username) {
      const result = await api.devLogin(email, username);
      await saveTokens(result);
      setToken(result.access_token);
      const profile = await api.getProfile();
      setProfileReady(Boolean(profile.username));
    },
    async loginWithGoogle(idToken) {
      const result = await api.googleLogin(idToken);
      await saveTokens(result);
      setToken(result.access_token);
      const profile = await api.getProfile();
      setProfileReady(Boolean(profile.username));
    },
    markProfileReady() { setProfileReady(true); },
    async logout() {
      const refreshToken = await SecureStore.getItemAsync('refresh_token');
      if (refreshToken) await api.logout(refreshToken).catch(() => null);
      await SecureStore.deleteItemAsync('access_token');
      await SecureStore.deleteItemAsync('refresh_token');
      setToken(null);
      setProfileReady(false);
    },
  }), [token, profileReady, loading]);

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession() {
  const context = useContext(SessionContext);
  if (!context) throw new Error('useSession must be used inside SessionProvider');
  return context;
}
