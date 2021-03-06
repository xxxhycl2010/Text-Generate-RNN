# coding:utf-8

import argparse
import sys
import os
import time
import numpy as np
import tensorflow as tf
from model import Model
from data_loader import Data
import io

BEGIN_CHAR = '<'
END_CHAR = '>'
UNKNOWN_CHAR = '*'

epochs = 1000
num_layers = 3
layers_size = 512
batch_size = 64
seq_len = 500

with open('setting.ini', 'a') as f:
    tim = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    f.write(tim)
    f.write('epochs: {}'.format(epochs))
    f.write('num_layers: {}'.format(num_layers))
    f.write('layers_size: {}'.format(layers_size))
    f.write('batch_size: {}'.format(batch_size))
    f.write('seq_len: {}'.format(seq_len))

data_dir = 'data/poetry/'
input_file = 'tang(simplified).txt'
vocab_file = 'vocab_tang(simplified).pkl'
tensor_file = 'tensor_tang(simplified).npy'

novel_data_dir = 'data/novel/'
novel_input_file = 'train_data.txt'
novel_vocab_file = 'vocab.pkl'
novel_tensor_file = 'tensor.npy'

model_dir = 'model'

if not os.path.exists(model_dir):
    os.mkdir(model_dir)

clas = 'novel'
is_continue_train = False

os.environ["CUDA_VISIBLE_DEVICES"] = "0"

def train(data, model):
    with tf.Session() as sess:
        sess.run(tf.global_variables_initializer())
        saver = tf.train.Saver(tf.global_variables(), max_to_keep=1)
        start = 0
        if is_continue_train:
            model_file = tf.train.latest_checkpoint(model_dir)
            saver.restore(sess, model_file)
            start = model.global_step.eval() // data.n_size + 1
            print('\nContinue train from epoch {}\n'.format(start))

        for epoch in range(start, epochs+start):
            sess.run(tf.assign(model.learning_rate, 0.01 * (0.97 ** epoch)))
            pointer = 0
            for batche in range(data.n_size):
                model.global_step.assign(epoch*data.n_size + batche).eval()
                feed_dict = {model.x_tf: data.x_batches[pointer], model.y_tf: data.y_batches[pointer]}
                
                train_loss, _, _, pre = sess.run(
                    [model.cost, model.final_state, model.train_op, model.pre], 
                    feed_dict=feed_dict)
                sys.stdout.write('\r')
                info = "{}/{} (epoch {}) | train_loss {:.5f} | learn_rate {:.5f}" \
                    .format(epoch * data.n_size + batche,
                            epochs * data.n_size, epoch, 
                            train_loss, sess.run(model.learning_rate))
                sys.stdout.write(info)

                if (epoch * data.n_size + batche) % 1000 == 0 \
                        or (epoch == epochs-1 and batche == data.n_size-1):
                    checkpoint_path = os.path.join(model_dir, clas + '_model.ckpt')
                    saver.save(sess, checkpoint_path, global_step=model.global_step)
                    sys.stdout.write('\n')
                    print("model saved to {}".format(checkpoint_path))
                
                if (epoch * data.n_size + batche) % 200 == 0 \
                        or (epoch == epochs-1 and batche == data.n_size-1):                    
                    sys.stdout.write('\n')

                    lis = '\n训练样本：\n'
                    words = list(map(data.id2char, data.x_batches[pointer][0][:100]))
                    for i in words:
                        lis += i
                    print(lis)

                    lis = '\n预测输出：\n'
                    words = list(map(data.id2char, pre[:100]))
                    for word in words:
                        lis += word
                    print(lis)
                    print('\nloss: ', str(train_loss))

                    with open('train_step.txt', 'a') as f:
                        tim = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                        text = '{}, loss: {}, step: {}, {}\n'.format(tim, train_loss, epoch*data.n_size+batche, lis)
                        f.write(text)
                pointer += 1 
            sys.stdout.write('\n')

def generate_text(data, sess, model, begin_char=''):
    poem = begin_char
    head = BEGIN_CHAR
    x = np.array([list(map(data.char2id, head))])
    state = sess.run(model.cell.zero_state(1, tf.float32))
    feed_dict = {model.x_tf: x, model.initial_state: state}
    [probs, state] = sess.run([model.probs, model.final_state], feed_dict)
    word = to_word(data, probs[-1])
    while word != END_CHAR:
        poem += word
        x = np.zeros((1, 1))
        x[0, 0] = data.char2id(word)
        [probs, state] = sess.run([model.probs, model.final_state],
                                  {model.x_tf: x, model.initial_state: state})
        word = to_word(data, probs[-1])
    return poem

def to_word(data, weights):
    t = np.cumsum(weights)
    s = np.sum(weights)
    sa = int(np.searchsorted(t, np.random.rand(1) * s))
    return data.id2char(sa)

def sample(data, model, head=u''):
    for word in head:
        if word not in data.words:
            return u'{} 不在字典中'.format(word)

    with tf.Session() as sess:
        sess.run(tf.global_variables_initializer())

        saver = tf.train.Saver(tf.global_variables())
        model_file = tf.train.latest_checkpoint(model_dir)
        saver.restore(sess, model_file)

        if head:
            print('生成藏头诗 ---> ', head)
            poem = BEGIN_CHAR + '《' + '》'
            for head_word in head:
                poem += head_word
                x = np.array([list(map(data.char2id, poem))])
                state = sess.run(model.cell.zero_state(1, tf.float32))
                feed_dict = {model.x_tf: x, model.initial_state: state}
                [probs, state] = sess.run([model.probs, model.final_state], feed_dict)
                word = to_word(data, probs[-1])
                while word != u'，' and word != u'。':
                    poem += word
                    x = np.zeros((1, 1))
                    x[0, 0] = data.char2id(word)
                    [probs, state] = sess.run([model.probs, model.final_state],
                                              {model.x_tf: x, model.initial_state: state})
                    word = to_word(data, probs[-1])
                poem += word
            return poem[1:]
        else:
            return generate_text(data, sess, model)


def main():
    msg = """
            Usage:
            Training: 
                python generate.py --mode train --clas novel
            Sampling:
                python generate.py --mode sample --head 明月别枝惊鹊
            """
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', type=str, default='sample',
                        help=u'usage: train, con-train or sample, sample is default')
    parser.add_argument('--head', type=str, default='',
                        help='生成藏头诗')

    parser.add_argument('--clas', type=str, default='',
                        help='novel or poetry')

    args = parser.parse_args()

    if args.mode == 'sample':
        infer = True
        data = Data(data_dir, input_file, vocab_file, 
            tensor_file, batch_size=batch_size)
        model = Model(data=data, infer=infer, 
            num_layers=num_layers, layers_size=layers_size)
        print(sample(data, model, head=args.head))
    elif args.mode == 'train' or args.mode == 'con-train':
        global is_continue_train
        if args.mode == 'con-train':
            is_continue_train = True
        infer = False
        global clas
        clas = args.clas
        if args.clas == 'novel':
            data = Data(novel_data_dir, novel_input_file, 
                novel_vocab_file, novel_tensor_file, seq_len=seq_len, batch_size=batch_size)
            model = Model(data=data, infer=infer, 
                num_layers=num_layers, layers_size=layers_size)
            print(train(data, model))  
        elif args.clas == 'poetry':
            data = Data(data_dir, input_file, vocab_file, 
                tensor_file, clas='poetry', batch_size=batch_size)
            model = Model(data=data, infer=infer, 
                num_layers=num_layers, layers_size=layers_size)
            print(train(data, model))
        else:
            print(msg)
    else:
        print(msg)


if __name__ == '__main__':
    main()
