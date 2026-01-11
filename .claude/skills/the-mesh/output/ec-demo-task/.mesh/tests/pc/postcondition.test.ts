/**
 * Auto-generated Post-Condition Tests from TRIR specification
 *
 * These tests verify that function implementations actually perform
 * the side effects (create/update/delete) specified in the spec.
 *
 * Tests use mock repositories - implementation must accept repository parameter.
 * @generated
 */

import { describe, it, expect } from '@jest/globals';

// Implementation imports
import { addToCart } from 'src.addToCart';
import { cancelOrder } from 'src.cancelOrder';
import { checkout } from 'src.checkout';
import { removeFromCart } from 'src.removeFromCart';

// ========== Repository Interfaces ==========

interface CartItemRepository {
  create(data: Partial<CartItem>): Promise<CartItem>;
  get(id: string): Promise<CartItem | null>;
  getAll(): Promise<CartItem[]>;
  update(id: string, data: Partial<CartItem>): Promise<CartItem>;
  delete(id: string): Promise<boolean>;
}

interface CartItem {
  id: string;
  [key: string]: unknown;
}

interface OrderRepository {
  create(data: Partial<Order>): Promise<Order>;
  get(id: string): Promise<Order | null>;
  getAll(): Promise<Order[]>;
  update(id: string, data: Partial<Order>): Promise<Order>;
  delete(id: string): Promise<boolean>;
}

interface Order {
  id: string;
  [key: string]: unknown;
}

interface ProductRepository {
  create(data: Partial<Product>): Promise<Product>;
  get(id: string): Promise<Product | null>;
  getAll(): Promise<Product[]>;
  update(id: string, data: Partial<Product>): Promise<Product>;
  delete(id: string): Promise<boolean>;
}

interface Product {
  id: string;
  [key: string]: unknown;
}

// ========== Mock Factories ==========

function createMockCartItemRepository(): CartItemRepository {
  const mockData: Record<string, CartItem> = {};
  return {
    create: jest.fn().mockImplementation((data) => Promise.resolve({ id: "NEW-001", ...data })),
    get: jest.fn().mockImplementation((id) => Promise.resolve(mockData[id] || null)),
    getAll: jest.fn().mockResolvedValue([]),
    update: jest.fn().mockImplementation((id, data) => Promise.resolve({ ...mockData[id], ...data })),
    delete: jest.fn().mockResolvedValue(true),
    _setData: (id: string, data: CartItem) => { mockData[id] = data; },
  };
}

function createMockOrderRepository(): OrderRepository {
  const mockData: Record<string, Order> = {};
  return {
    create: jest.fn().mockImplementation((data) => Promise.resolve({ id: "NEW-001", ...data })),
    get: jest.fn().mockImplementation((id) => Promise.resolve(mockData[id] || null)),
    getAll: jest.fn().mockResolvedValue([]),
    update: jest.fn().mockImplementation((id, data) => Promise.resolve({ ...mockData[id], ...data })),
    delete: jest.fn().mockResolvedValue(true),
    _setData: (id: string, data: Order) => { mockData[id] = data; },
  };
}

function createMockProductRepository(): ProductRepository {
  const mockData: Record<string, Product> = {};
  return {
    create: jest.fn().mockImplementation((data) => Promise.resolve({ id: "NEW-001", ...data })),
    get: jest.fn().mockImplementation((id) => Promise.resolve(mockData[id] || null)),
    getAll: jest.fn().mockResolvedValue([]),
    update: jest.fn().mockImplementation((id, data) => Promise.resolve({ ...mockData[id], ...data })),
    delete: jest.fn().mockResolvedValue(true),
    _setData: (id: string, data: Product) => { mockData[id] = data; },
  };
}

// ========== Post-Condition Tests ==========

describe('PostCondition: addToCart', () => {

  it('addToCart: should create CartItem with specified fields', async () => {
    // Arrange
    const repository = createMockCartItemRepository();
    const inputData = { cartId: "CARTID-001", productId: "PRODUCTID-001", quantity: 100 };

    // Act
    const result = await addToCart(inputData, { repository });

    // Assert
    expect(repository.create).toHaveBeenCalledTimes(1);
    const callArgs = repository.create.mock.calls[0][0];

    expect(callArgs).toHaveProperty("id");
    expect(callArgs.id).toBe("$expr");
    expect(callArgs).toHaveProperty("cartId");
    expect(callArgs.cartId).toBe(inputData.None);
    expect(callArgs).toHaveProperty("productId");
    expect(callArgs.productId).toBe(inputData.None);
    expect(callArgs).toHaveProperty("quantity");
    expect(callArgs.quantity).toBe(inputData.None);
    expect(callArgs).toHaveProperty("unitPrice");
    expect(callArgs.unitPrice).toBe("$expr");
  });

  it('addToCart: should update Product with specified fields', async () => {
    // Arrange
    const repository = createMockProductRepository();
    const inputData = { cartId: "CARTID-001", productId: "PRODUCTID-001", quantity: 100 };
    const existing = { id: "PRODUCT-001", name: "NAME-001", price: 100, stock: 100 };
    repository._setData(existing.id, existing);
    repository.get.mockResolvedValue(existing);

    // Act
    const result = await addToCart(inputData, { repository });

    // Assert
    expect(repository.update).toHaveBeenCalledTimes(1);
    const [updateId, updateData] = repository.update.mock.calls[0];

    expect(updateData).toHaveProperty("stock");
    expect(updateData.stock).toBe("$expr");
  });
});

describe('PostCondition: removeFromCart', () => {

  it('removeFromCart: should update Product with specified fields', async () => {
    // Arrange
    const repository = createMockProductRepository();
    const inputData = { cartItemId: "CARTITEMID-001" };
    const existing = { id: "PRODUCT-001", name: "NAME-001", price: 100, stock: 100 };
    repository._setData(existing.id, existing);
    repository.get.mockResolvedValue(existing);

    // Act
    const result = await removeFromCart(inputData, { repository });

    // Assert
    expect(repository.update).toHaveBeenCalledTimes(1);
    const [updateId, updateData] = repository.update.mock.calls[0];

    expect(updateData).toHaveProperty("stock");
    expect(updateData.stock).toBe("$expr");
  });

  it('removeFromCart: should delete CartItem', async () => {
    // Arrange
    const repository = createMockCartItemRepository();
    const inputData = { cartItemId: "CARTITEMID-001" };
    const existing = { id: "CARTITEM-001", cartId: "CARTID-001", productId: "PRODUCTID-001", quantity: 100, unitPrice: 100 };
    repository._setData(existing.id, existing);
    repository.get.mockResolvedValue(existing);

    // Act
    const result = await removeFromCart(inputData, { repository });

    // Assert
    expect(repository.delete).toHaveBeenCalledTimes(1);
    expect(repository.delete).toHaveBeenCalledWith(existing.id);
  });
});

describe('PostCondition: checkout', () => {

  it('checkout: should create Order with specified fields', async () => {
    // Arrange
    const repository = createMockOrderRepository();
    const inputData = { cartId: "CARTID-001", userId: "USERID-001" };

    // Act
    const result = await checkout(inputData, { repository });

    // Assert
    expect(repository.create).toHaveBeenCalledTimes(1);
    const callArgs = repository.create.mock.calls[0][0];

    expect(callArgs).toHaveProperty("id");
    expect(callArgs.id).toBe("$expr");
    expect(callArgs).toHaveProperty("userId");
    expect(callArgs.userId).toBe(inputData.None);
    expect(callArgs).toHaveProperty("totalAmount");
    expect(callArgs.totalAmount).toBe(0);
    expect(callArgs).toHaveProperty("status");
    expect(callArgs.status).toBe("PENDING");
    expect(callArgs).toHaveProperty("createdAt");
    expect(callArgs.createdAt).toBe("$expr");
  });
});

describe('PostCondition: cancelOrder', () => {

  it('cancelOrder: should update Order with specified fields', async () => {
    // Arrange
    const repository = createMockOrderRepository();
    const inputData = { orderId: "ORDERID-001" };
    const existing = { id: "ORDER-001", userId: "USERID-001", totalAmount: 100, status: "STATUS-001", createdAt: "2024-01-01T00:00:00Z" };
    repository._setData(existing.id, existing);
    repository.get.mockResolvedValue(existing);

    // Act
    const result = await cancelOrder(inputData, { repository });

    // Assert
    expect(repository.update).toHaveBeenCalledTimes(1);
    const [updateId, updateData] = repository.update.mock.calls[0];

    expect(updateData).toHaveProperty("status");
    expect(updateData.status).toBe("CANCELLED");
  });
});
