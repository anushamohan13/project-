import React from 'react';
import { ActivityIndicator, Pressable, Text } from 'react-native';
import { palette, radius, spacing } from '../theme/tokens';

export default function PrimaryButton({ title, onPress, loading = false, disabled = false }) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={title}
      disabled={disabled || loading}
      onPress={onPress}
      style={({ pressed }) => ({
        backgroundColor: disabled ? '#A7A7A7' : palette.blue,
        borderRadius: radius.md,
        padding: spacing.md,
        opacity: pressed ? 0.75 : 1,
        alignItems: 'center',
      })}
    >
      {loading ? <ActivityIndicator color="white" /> : <Text style={{ color: 'white', fontSize: 17, fontWeight: '700' }}>{title}</Text>}
    </Pressable>
  );
}
