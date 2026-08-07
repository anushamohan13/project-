import React, { useEffect, useState } from 'react';
import { Alert, KeyboardAvoidingView, Platform, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import * as Google from 'expo-auth-session/providers/google';
import * as WebBrowser from 'expo-web-browser';

import FormField from '../components/FormField';
import PrimaryButton from '../components/PrimaryButton';
import { useSession } from '../store/SessionContext';
import { spacing } from '../theme/tokens';

WebBrowser.maybeCompleteAuthSession();

export default function LoginScreen() {
  const { login, loginWithGoogle } = useSession();
  const [email, setEmail] = useState('demo@example.com');
  const [username, setUsername] = useState('demo_user');
  const [loading, setLoading] = useState(false);
  const googleConfigured = Boolean(
    process.env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID || process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID,
  );
  const [request, response, promptAsync] = Google.useIdTokenAuthRequest({
    iosClientId: process.env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID,
    androidClientId: process.env.EXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID,
    webClientId: process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID,
  });

  useEffect(() => {
    if (response?.type !== 'success') return;
    const idToken = response.authentication?.idToken || response.params?.id_token;
    if (!idToken) {
      Alert.alert('Google sign-in failed', 'Google did not return an ID token. Check the OAuth client configuration.');
      return;
    }
    setLoading(true);
    loginWithGoogle(idToken)
      .catch((error) => Alert.alert('Google sign-in failed', error.message))
      .finally(() => setLoading(false));
  }, [response, loginWithGoogle]);

  async function submit() {
    setLoading(true);
    try { await login(email.trim(), username.trim()); }
    catch (error) { Alert.alert('Sign-in failed', error.message); }
    finally { setLoading(false); }
  }

  return (
    <SafeAreaView style={{ flex: 1 }}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1, justifyContent: 'center', padding: spacing.lg }}>
        <Text style={{ fontSize: 42, fontWeight: '800', marginBottom: spacing.sm }}>PocketPilot</Text>
        <Text style={{ fontSize: 18, color: '#666', marginBottom: spacing.xl }}>Plan spending, savings, and important purchases with confirmation-safe AI assistance.</Text>
        <View style={{ borderRadius: 20, padding: spacing.lg, backgroundColor: 'rgba(142,142,147,0.12)' }}>
          <PrimaryButton
            title={googleConfigured ? 'Continue with Google' : 'Configure Google OAuth to continue'}
            onPress={() => promptAsync()}
            loading={loading}
            disabled={!request || !googleConfigured}
          />
          <Text style={{ textAlign: 'center', marginVertical: spacing.md, color: '#777' }}>or use development mode</Text>
          <FormField label="Email" value={email} onChangeText={setEmail} keyboardType="email-address" />
          <FormField label="Username" value={username} onChangeText={setUsername} />
          <PrimaryButton title="Continue in development mode" onPress={submit} loading={loading} />
          <Text style={{ fontSize: 12, color: '#777', marginTop: spacing.md }}>Development login is automatically disabled when the backend runs in production.</Text>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
