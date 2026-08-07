import React from 'react';
import { Text, TextInput, View } from 'react-native';
import { spacing } from '../theme/tokens';

export default function FormField({ label, value, onChangeText, keyboardType = 'default', placeholder, secureTextEntry = false }) {
  return (
    <View style={{ marginBottom: spacing.md }}>
      <Text style={{ fontSize: 13, fontWeight: '600', marginBottom: spacing.xs }}>{label}</Text>
      <TextInput
        accessibilityLabel={label}
        value={value}
        onChangeText={onChangeText}
        keyboardType={keyboardType}
        placeholder={placeholder}
        secureTextEntry={secureTextEntry}
        autoCapitalize="none"
        style={{ borderWidth: 1, borderColor: '#C7C7CC', borderRadius: 12, padding: 14, fontSize: 16 }}
      />
    </View>
  );
}
