/**
 * EC Demo Types - Generated from TRIR Spec
 */

// Entity Types
export interface Product {
  id: string;
  name: string;
  price: number;
  stock: number;
}

export interface Cart {
  id: string;
  userId: string;
  totalAmount?: number;
}

export interface CartItem {
  id: string;
  cartId: string;
  productId: string;
  quantity: number;
  unitPrice: number;
}

export interface Order {
  id: string;
  userId: string;
  totalAmount: number;
  status: 'PENDING' | 'PAID' | 'SHIPPED' | 'DELIVERED' | 'CANCELLED';
  createdAt: Date;
}

export interface OrderItem {
  id: string;
  orderId: string;
  productId: string;
  productName: string;
  quantity: number;
  unitPrice: number;
}

// Repository Interfaces
export interface Repository<T> {
  create(data: Partial<T>): Promise<T>;
  get(id: string): Promise<T | null>;
  getAll(): Promise<T[]>;
  update(id: string, data: Partial<T>): Promise<T>;
  delete(id: string): Promise<boolean>;
}

export interface ProductRepository extends Repository<Product> {}
export interface CartRepository extends Repository<Cart> {}
export interface CartItemRepository extends Repository<CartItem> {
  findByCartId(cartId: string): Promise<CartItem[]>;
}
export interface OrderRepository extends Repository<Order> {}
export interface OrderItemRepository extends Repository<OrderItem> {}

// Context
export interface RepositoryContext {
  productRepository: ProductRepository;
  cartRepository: CartRepository;
  cartItemRepository: CartItemRepository;
  orderRepository: OrderRepository;
  orderItemRepository: OrderItemRepository;
}

// Helper functions
export function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}

export function now(): Date {
  return new Date();
}

// Errors
export class InvalidQuantityError extends Error {
  code = 'INVALID_QUANTITY';
  status = 400;
  constructor() { super('Invalid quantity'); }
}

export class OutOfStockError extends Error {
  code = 'OUT_OF_STOCK';
  status = 400;
  constructor() { super('Out of stock'); }
}

export class ProductNotFoundError extends Error {
  code = 'PRODUCT_NOT_FOUND';
  status = 404;
  constructor() { super('Product not found'); }
}

export class CartItemNotFoundError extends Error {
  code = 'CART_ITEM_NOT_FOUND';
  status = 404;
  constructor() { super('Cart item not found'); }
}

export class OrderNotFoundError extends Error {
  code = 'ORDER_NOT_FOUND';
  status = 404;
  constructor() { super('Order not found'); }
}

export class CannotCancelError extends Error {
  code = 'CANNOT_CANCEL';
  status = 400;
  constructor() { super('Cannot cancel this order'); }
}
