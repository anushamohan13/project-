import React, { useEffect, useState } from 'react';
import { Alert, ScrollView, Switch, Text, View } from 'react-native';

import { api } from '../api/client';
import FormField from '../components/FormField';
import PrimaryButton from '../components/PrimaryButton';
import { spacing } from '../theme/tokens';

export default function CategoriesScreen() {
  const [name, setName] = useState('Pets');
  const [essential, setEssential] = useState(false);
  const [items, setItems] = useState([]);

  async function load() {
    try { setItems(await api.listCategories()); }
    catch (error) { Alert.alert('Could not load categories', error.message); }
  }
  useEffect(() => { load(); }, []);

  async function add() {
    try {
      await api.createCategory({ name, icon: 'tag', color_token: null, is_essential: essential, is_active: true });
      setName('');
      await load();
    } catch (error) { Alert.alert('Could not add category', error.message); }
  }

  async function remove(id) {
    try { await api.deleteCategory(id); await load(); }
    catch (error) { Alert.alert('Could not delete category', error.message); }
  }

  return (
    <ScrollView contentContainerStyle={{ padding: spacing.lg }} keyboardShouldPersistTaps="handled">
      <FormField label="Category name" value={name} onChangeText={setName} />
      <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: spacing.md }}>
        <Text>Protect as essential</Text>
        <Switch value={essential} onValueChange={setEssential} />
      </View>
      <PrimaryButton title="Create category" onPress={add} disabled={!name.trim()} />
      <View style={{ marginTop: spacing.xl }}>
        {items.map((item) => (
          <View key={item.id} style={{ padding: spacing.md, borderRadius: 16, backgroundColor: 'rgba(142,142,147,0.12)', marginBottom: spacing.md }}>
            <Text style={{ fontWeight: '800', fontSize: 17 }}>{item.name}</Text>
            <Text style={{ color: '#666', marginBottom: spacing.sm }}>{item.is_essential ? 'Essential category' : 'Flexible category'}</Text>
            <PrimaryButton title="Delete category" onPress={() => remove(item.id)} />
          </View>
        ))}
      </View>
    </ScrollView>
  );
}
