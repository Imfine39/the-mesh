/**
 * EC Demo - Repository Interfaces
 *
 * Repository pattern for data access abstraction
 */

import { Product, Cart, CartItem, Order, OrderItem } from './types';

export interface Repository<T> {
  get(id: string): Promise<T | null>;
  create(entity: T): Promise<T>;
  update(id: string, data: Partial<T>): Promise<T>;
  delete(id: string): Promise<boolean>;
  findBy(query: Partial<T>): Promise<T[]>;
}

export interface ProductRepository extends Repository<Product> {}
export interface CartRepository extends Repository<Cart> {}
export interface CartItemRepository extends Repository<CartItem> {
  findByCartId(cartId: string): Promise<CartItem[]>;
}
export interface OrderRepository extends Repository<Order> {}
export interface OrderItemRepository extends Repository<OrderItem> {
  findByOrderId(orderId: string): Promise<OrderItem[]>;
}

// === Context for Dependency Injection ===

export interface RepositoryContext {
  products: ProductRepository;
  carts: CartRepository;
  cartItems: CartItemRepository;
  orders: OrderRepository;
  orderItems: OrderItemRepository;
}

// === Utility Functions ===

export function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}

export function now(): Date {
  return new Date();
}
