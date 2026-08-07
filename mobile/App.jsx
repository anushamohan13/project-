import React from 'react';
import { NavigationContainer, DefaultTheme, DarkTheme } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { useColorScheme } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import * as Notifications from 'expo-notifications';

import { SessionProvider, useSession } from './src/store/SessionContext';
import LoginScreen from './src/screens/LoginScreen';
import OnboardingScreen from './src/screens/OnboardingScreen';
import DashboardScreen from './src/screens/DashboardScreen';
import PlanHistoryScreen from './src/screens/PlanHistoryScreen';
import PlannerScreen from './src/screens/PlannerScreen';
import TransactionsScreen from './src/screens/TransactionsScreen';
import CategoriesScreen from './src/screens/CategoriesScreen';
import WishlistScreen from './src/screens/WishlistScreen';
import AssistantScreen from './src/screens/AssistantScreen';
import SettingsScreen from './src/screens/SettingsScreen';

Notifications.setNotificationHandler({
  handleNotification: async () => ({ shouldShowBanner: true, shouldShowList: true, shouldPlaySound: false, shouldSetBadge: false }),
});

const RootStack = createNativeStackNavigator();
const DashboardStack = createNativeStackNavigator();
const TransactionStack = createNativeStackNavigator();
const Tabs = createBottomTabNavigator();

function DashboardNavigator() {
  return (
    <DashboardStack.Navigator>
      <DashboardStack.Screen name="DashboardHome" component={DashboardScreen} options={{ title: 'Dashboard', headerLargeTitle: true }} />
      <DashboardStack.Screen name="PlanHistory" component={PlanHistoryScreen} options={{ title: 'Plan history' }} />
    </DashboardStack.Navigator>
  );
}

function TransactionNavigator() {
  return (
    <TransactionStack.Navigator>
      <TransactionStack.Screen name="TransactionsHome" component={TransactionsScreen} options={{ title: 'Transactions', headerLargeTitle: true }} />
      <TransactionStack.Screen name="Categories" component={CategoriesScreen} options={{ title: 'Custom categories' }} />
    </TransactionStack.Navigator>
  );
}

function MainTabs() {
  return (
    <Tabs.Navigator screenOptions={{ headerLargeTitle: true }}>
      <Tabs.Screen name="Dashboard" component={DashboardNavigator} options={{ headerShown: false }} />
      <Tabs.Screen name="Planner" component={PlannerScreen} />
      <Tabs.Screen name="Transactions" component={TransactionNavigator} options={{ headerShown: false }} />
      <Tabs.Screen name="Wishlist" component={WishlistScreen} />
      <Tabs.Screen name="Assistant" component={AssistantScreen} />
      <Tabs.Screen name="Settings" component={SettingsScreen} />
    </Tabs.Navigator>
  );
}

function RootNavigator() {
  const { token, profileReady, loading } = useSession();
  if (loading) return null;
  return (
    <RootStack.Navigator screenOptions={{ headerBackTitle: 'Back' }}>
      {!token ? (
        <RootStack.Screen name="Login" component={LoginScreen} options={{ headerShown: false }} />
      ) : !profileReady ? (
        <RootStack.Screen name="Onboarding" component={OnboardingScreen} options={{ title: 'Set up PocketPilot' }} />
      ) : (
        <RootStack.Screen name="Main" component={MainTabs} options={{ headerShown: false }} />
      )}
    </RootStack.Navigator>
  );
}

export default function App() {
  const scheme = useColorScheme();
  return (
    <SafeAreaProvider>
      <SessionProvider>
        <NavigationContainer theme={scheme === 'dark' ? DarkTheme : DefaultTheme}>
          <StatusBar style="auto" />
          <RootNavigator />
        </NavigationContainer>
      </SessionProvider>
    </SafeAreaProvider>
  );
}
