import React, { useEffect, useState } from 'react';
import { Alert, ScrollView, Text, View } from 'react-native';
import FormField from '../components/FormField';
import PrimaryButton from '../components/PrimaryButton';
import { api } from '../api/client';
import { spacing } from '../theme/tokens';

export default function WishlistScreen() {
  const [name, setName] = useState('New laptop');
  const [price, setPrice] = useState('1500');
  const [target, setTarget] = useState('2026-12-15');
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);

  async function load() { try { setItems(await api.listWishlist()); } catch { setItems([]); } }
  useEffect(() => { load(); }, []);

  async function add() {
    setLoading(true);
    try {
      await api.createWishlist({
        name, description: null, category: 'Technology', product_link: null, image_url: null,
        price, currency: 'SGD', target_purchase_date: target, priority: 'high', amount_saved: '0', automatic_recommendations: true,
      });
      await load();
    } catch (error) { Alert.alert('Could not add item', error.message); }
    finally { setLoading(false); }
  }

  return (
    <ScrollView contentContainerStyle={{ padding: spacing.lg }} keyboardShouldPersistTaps="handled">
      <FormField label="Wishlist item" value={name} onChangeText={setName} />
      <FormField label="Price" value={price} onChangeText={setPrice} keyboardType="decimal-pad" />
      <FormField label="Target date (YYYY-MM-DD)" value={target} onChangeText={setTarget} />
      <PrimaryButton title="Add Smart Wishlist goal" onPress={add} loading={loading} />
      <View style={{ marginTop: spacing.xl }}>
        {items.map((item) => (
          <View key={item.id} style={{ padding: spacing.md, borderRadius: 16, backgroundColor: 'rgba(142,142,147,0.12)', marginBottom: spacing.md }}>
            <Text style={{ fontSize: 18, fontWeight: '700' }}>{item.name}</Text>
            <Text>{item.currency} {item.price} · {item.progress_percent}% saved</Text>
            <Text>Required weekly contribution: {item.currency} {item.required_weekly_contribution}</Text>
          </View>
        ))}
      </View>
    </ScrollView>
  );
}
